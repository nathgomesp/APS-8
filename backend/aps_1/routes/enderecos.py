# routes/enderecos.py
from flask import Blueprint, request, jsonify
from models import db, Localizacao
from routes.air_quality import geocode_address
from services.notifications import get_health_recommendations
import requests

enderecos_bp = Blueprint('enderecos', __name__)

@enderecos_bp.route('/enderecos', methods=['POST'])
def salvar_endereco():
    data = request.get_json()
    nome_local = data.get('nome_local')
    endereco_texto = data.get('endereco')  # opcional
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    id_usuario = data.get('id_usuario')
    aqi_limite = data.get('aqi_limite', 150)

    if not nome_local or not id_usuario:
        return jsonify({'error': 'nome_local e id_usuario são obrigatórios'}), 400

    # se não vier lat/lon, tenta geocode
    if (latitude is None or longitude is None) and endereco_texto:
        lat, lon = geocode_address(endereco_texto)
        if not lat or not lon:
            return jsonify({'error': 'Endereço inválido ou não encontrado'}), 400
        latitude, longitude = float(lat), float(lon)
    elif latitude is None or longitude is None:
        return jsonify({'error': 'Forneça latitude/longitude ou endereco'}), 400

    novo = Localizacao(
        id_usuario=int(id_usuario),
        nome_local=nome_local,
        latitude=float(latitude),
        longitude=float(longitude),
        aqi_limite=int(aqi_limite)
    )
    db.session.add(novo)
    db.session.commit()

    return jsonify({
        'id_localizacao': novo.id_localizacao,
        'id_usuario': novo.id_usuario,
        'nome_local': novo.nome_local,
        'latitude': novo.latitude,
        'longitude': novo.longitude,
        'aqi_limite': novo.aqi_limite
    }), 201

@enderecos_bp.route('/enderecos', methods=['GET'])
def listar_enderecos():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id é obrigatório'}), 400

    locais = Localizacao.query.filter_by(id_usuario=int(user_id)).all()
    result = [{
        'id_localizacao': l.id_localizacao,
        'id_usuario': l.id_usuario,
        'nome_local': l.nome_local,
        'latitude': l.latitude,
        'longitude': l.longitude,
        'aqi_limite': l.aqi_limite
    } for l in locais]
    return jsonify(result), 200

@enderecos_bp.route('/enderecos/<int:id>/aqi', methods=['GET'])
def get_local_aqi(id):
    loc = Localizacao.query.get_or_404(id)
    lat, lon = loc.latitude, loc.longitude

    # chama WAQI
    token = 'b0ede179c7f377076245b3840a175c93ebef527d'  # pode mover p/ env var depois
    url = f'https://api.waqi.info/feed/geo:{lat};{lon}/?token={token}'
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        if data.get('status') != 'ok':
            return jsonify({'error': 'Dados WAQI não disponíveis'}), 404

        aqi = data['data'].get('aqi')
        recommendations = get_health_recommendations(aqi if isinstance(aqi, int) else 0)
        return jsonify({
            'id_localizacao': loc.id_localizacao,
            'nome_local': loc.nome_local,
            'latitude': loc.latitude,
            'longitude': loc.longitude,
            'aqi': aqi,
            'aqi_limite': loc.aqi_limite,
            'recomendacoes': recommendations
        }), 200
    except requests.RequestException as e:
        return jsonify({'error': 'Erro ao acessar WAQI'}), 500
