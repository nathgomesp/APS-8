# alerts.py
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from services.notifications import send_push_notification, get_health_recommendations

alerts_bp = Blueprint('alerts', __name__)

DB_PATH = "alerts.sqlite"
INTERVAL_MINUTES = 15        # periodicidade da checagem global
COOLDOWN_SECONDS = 60 * 60   # evitar spam: 1 hora entre notificações por alerta

_lock = threading.Lock()
_scheduler = None

# --- DB helpers --------------------------------------------------------------
def init_db():
    with _lock, sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                location TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                aqi_limit REAL NOT NULL,
                device_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_notified_at TEXT
            )
        ''')
        conn.commit()

def insert_alert(alert):
    with _lock, sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO alerts (user_id, location, lat, lon, aqi_limit, device_token, created_at, last_notified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alert['user_id'],
            alert['location'],
            float(alert['lat']),
            float(alert['lon']),
            float(alert['aqi_limit']),
            alert['device_token'],
            datetime.utcnow().isoformat(),
            None
        ))
        conn.commit()
        return cur.lastrowid

def fetch_all_alerts():
    with _lock, sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('SELECT id, user_id, location, lat, lon, aqi_limit, device_token, created_at, last_notified_at FROM alerts')
        rows = cur.fetchall()
        alerts = []
        for r in rows:
            alerts.append({
                'id': r[0],
                'user_id': r[1],
                'location': r[2],
                'lat': r[3],
                'lon': r[4],
                'aqi_limit': r[5],
                'device_token': r[6],
                'created_at': r[7],
                'last_notified_at': r[8]
            })
        return alerts

def update_last_notified(alert_id):
    with _lock, sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('UPDATE alerts SET last_notified_at = ? WHERE id = ?', (datetime.utcnow().isoformat(), alert_id))
        conn.commit()

# --- AQI helpers -------------------------------------------------------------
def fetch_aqi_for_coords(lat, lon, waqi_token=None):
    """
    Tenta consultar WAQI; se falhar, tenta OpenAQ.
    Retorna número (int/float) ou None.
    """
    try:
        if waqi_token:
            url = f'https://api.waqi.info/feed/geo:{lat};{lon}/'
            r = requests.get(url, params={'token': waqi_token}, timeout=10)
            r.raise_for_status()
            payload = r.json()
            if payload.get('status') == 'ok':
                aqi = payload.get('data', {}).get('aqi')
                try:
                    return int(aqi) if aqi is not None else None
                except (ValueError, TypeError):
                    return None

        # Fallback: OpenAQ latest (pega primeiro measurement.value)
        url2 = f'https://api.openaq.org/v2/latest?coordinates={lat},{lon}'
        r2 = requests.get(url2, timeout=10)
        r2.raise_for_status()
        results = r2.json().get('results', [])
        if results and 'measurements' in results[0] and results[0]['measurements']:
            value = results[0]['measurements'][0].get('value')
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
    except requests.RequestException as e:
        # current_app may not be available in some contexts; guard logging
        try:
            current_app.logger.debug(f"Erro ao buscar AQI: {e}")
        except Exception:
            pass
        return None
    return None

# --- Notification logic ------------------------------------------------------
def check_alert_and_maybe_notify(alert, waqi_token=None):
    """
    Verifica o AQI para o alerta e envia notificação se ultrapassar o limite,
    respeitando cooldown para evitar spam.
    """
    aqi = fetch_aqi_for_coords(alert['lat'], alert['lon'], waqi_token=waqi_token)
    if aqi is None:
        try:
            current_app.logger.debug(f"Não foi possível obter AQI para alert id={alert.get('id')}")
        except Exception:
            pass
        return False

    try:
        limit = float(alert['aqi_limit'])
    except (TypeError, ValueError):
        return False

    # checar cooldown
    last = alert.get('last_notified_at')
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if datetime.utcnow() - last_dt < timedelta(seconds=COOLDOWN_SECONDS):
                try:
                    current_app.logger.debug(f"Alert id={alert['id']} em cooldown; pulando.")
                except Exception:
                    pass
                return False
        except Exception:
            # formato inválido, continua normalmente
            pass

    if aqi > limit:
        recommendations = get_health_recommendations(aqi)
        body = f"AQI atual: {aqi}. Recomendações: {'; '.join(recommendations)}"
        try:
            send_push_notification(alert['device_token'], "Alerta de qualidade do ar", body)
            update_last_notified(alert['id'])
            try:
                current_app.logger.info(f"Notificação enviada para alert id={alert['id']}")
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                current_app.logger.error(f"Falha ao enviar notificação para alert id={alert['id']}: {e}")
            except Exception:
                pass
            return False
    return False

def run_periodic_check():
    """
    Função executada pelo scheduler: varre todos os alerts e checa cada um.
    """
    # garante contexto da app para usar current_app e configs
    try:
        with current_app.app_context():
            waqi_token = current_app.config.get('WAQI_TOKEN')  # opcional
            alerts = fetch_all_alerts()
            current_app.logger.info(f"Iniciando checagem de {len(alerts)} alert(s)")
            for alert in alerts:
                try:
                    check_alert_and_maybe_notify(alert, waqi_token=waqi_token)
                except Exception as e:
                    current_app.logger.exception(f"Erro checando alert id={alert.get('id')}: {e}")
    except RuntimeError:
        # se não houver app context disponível, tenta usar current_app directly
        try:
            waqi_token = current_app.config.get('WAQI_TOKEN')
            alerts = fetch_all_alerts()
            for alert in alerts:
                check_alert_and_maybe_notify(alert, waqi_token=waqi_token)
        except Exception:
            pass

# --- Scheduler init function (call this from app.py after registering blueprint) ----
def init_alerts(app):
    """
    Inicializa o DB local e inicia o scheduler de checagem periódica.
    Deve ser chamado a partir do app principal APÓS registrar o blueprint.
    Exemplo em app.py:
        from routes.alerts import alerts_bp, init_alerts
        app.register_blueprint(alerts_bp)
        init_alerts(app)
    """
    global _scheduler
    # Proteção contra reloader do Flask: só inicializa no processo principal
    # Werkzeug define WERKZEUG_RUN_MAIN no processo filho; queremos só o processo "real".
    is_reloader = bool(__import__('os').environ.get('WERKZEUG_RUN_MAIN'))
    if is_reloader:
        # se estivermos no processo do reloader secundário, continuar (evita duplicação)
        pass

    with app.app_context():
        init_db()
        if _scheduler is None:
            _scheduler = BackgroundScheduler()
            _scheduler.add_job(run_periodic_check, 'interval', minutes=INTERVAL_MINUTES, next_run_time=datetime.utcnow())
            _scheduler.start()
            app.logger.info("Scheduler de alerts iniciado")

# --- Blueprint endpoints -----------------------------------------------------
@alerts_bp.route('/alerts', methods=['POST'])
def create_alert():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON inválido'}), 400

    required_fields = ['user_id', 'location', 'lat', 'lon', 'aqi_limit', 'device_token']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Campos obrigatórios ausentes'}), 400

    # validar tipos básicos
    try:
        lat = float(data['lat'])
        lon = float(data['lon'])
        aqi_limit = float(data['aqi_limit'])
    except (TypeError, ValueError):
        return jsonify({'error': 'lat, lon e aqi_limit devem ser numéricos'}), 400

    # salvar no banco
    alert_id = insert_alert({
        'user_id': int(data['user_id']),
        'location': str(data['location']),
        'lat': lat,
        'lon': lon,
        'aqi_limit': aqi_limit,
        'device_token': str(data['device_token'])
    })

    # responder com o registro salvo (inclui id)
    saved = {
        'id': alert_id,
        'user_id': int(data['user_id']),
        'location': data['location'],
        'lat': lat,
        'lon': lon,
        'aqi_limit': aqi_limit,
        'device_token': data['device_token']
    }

    # Checagem imediata: se passar do limite, envia notificação
    try:
        waqi_token = current_app.config.get('WAQI_TOKEN')
        saved_db = dict(saved)
        saved_db['last_notified_at'] = None
        check_alert_and_maybe_notify(saved_db, waqi_token=waqi_token)
    except Exception as e:
        try:
            current_app.logger.exception(f"Erro na checagem imediata do alerta id={alert_id}: {e}")
        except Exception:
            pass

    return jsonify({'message': 'Alerta salvo com sucesso', 'alert': saved}), 201

@alerts_bp.route('/alerts', methods=['GET'])
def list_alerts():
    alerts = fetch_all_alerts()
    return jsonify(alerts), 200

@alerts_bp.route('/alerts/<int:alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    with _lock, sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('DELETE FROM alerts WHERE id = ?', (alert_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Alerta não encontrado'}), 404
    return jsonify({'message': 'Alerta removido'}), 200
