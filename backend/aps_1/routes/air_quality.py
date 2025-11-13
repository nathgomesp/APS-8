from flask import Blueprint, request, jsonify
import requests
import os

air_quality_bp = Blueprint('air_quality', __name__)

WAQI_TOKEN = os.environ.get('WAQI_TOKEN', 'b0ede179c7f377076245b3840a175c93ebef527d')
USER_AGENT = 'air-quality-app/1.0 (+https://example.com)'

def geocode_address(address):
    url = 'https://nominatim.openstreetmap.org/search'
    headers = {'User-Agent': USER_AGENT}
    params = {'q': address, 'format': 'json', 'limit': 1}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return data[0].get('lat'), data[0].get('lon')
    except requests.RequestException as e:
        print(f"Erro no geocode (Nominatim): {e}")
    return None, None

@air_quality_bp.route('/air-quality', methods=['GET'])
def get_air_quality():
    # aceita address (texto) OU lat & lon (coordenadas)
    address = request.args.get('address')
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not address and (not lat or not lon):
        return jsonify({'error': 'Parâmetro obrigatório: address OU lat + lon'}), 400

    # se vier address, geocodifica (tratando acentos/espacos via params)
    if address:
        lat, lon = geocode_address(address)
        if not lat or not lon:
            return jsonify({'error': 'Endereço não encontrado'}), 404

    # agora lat/lon devem estar preenchidos (string)
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return jsonify({'error': 'Latitude/longitude inválidas'}), 400

    # chama WAQI usando a coordenada
    waqi_url = f'https://api.waqi.info/feed/geo:{lat_f};{lon_f}/'
    params = {'token': WAQI_TOKEN}
    headers = {'User-Agent': USER_AGENT}

    try:
        r = requests.get(waqi_url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        payload = r.json()

        if payload.get('status') != 'ok':
            return jsonify({'error': 'Dados de qualidade do ar não disponíveis'}), 404

        data = payload.get('data', {})

        # extrair AQI com tratamento caso não seja número
        raw_aqi = data.get('aqi')
        try:
            aqi = int(raw_aqi)
        except (TypeError, ValueError):
            # WAQI às vezes retorna '-' ou null; tratar como None
            aqi = None

        city = None
        if isinstance(data.get('city'), dict):
            city = data['city'].get('name')

        dominentpol = data.get('dominentpol')
        iaqi = data.get('iaqi', {})

        measurements = []
        for param, value in iaqi.items():
            measurements.append({
                'parameter': param,
                'value': value.get('v') if isinstance(value, dict) else value,
                'unit': 'N/A'
            })

        return jsonify({
            'location': city,
            'aqi': aqi,
            'dominentpol': dominentpol,
            'measurements': measurements,
            'lat': lat_f,
            'lon': lon_f
        }), 200

    except requests.RequestException as e:
        print(f"Erro ao acessar WAQI: {e}")
        return jsonify({'error': 'Erro ao acessar WAQI'}), 500
