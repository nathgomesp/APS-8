from flask import Blueprint, request, jsonify
from models import db, Usuario

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/usuarios', methods=['POST'])
def cadastrar_usuario():
    data = request.get_json()
    nome = data.get('nome')
    token = data.get('device_token')

    if not nome or not token:
        return jsonify({'error': 'Nome e token são obrigatórios'}), 400

    novo_usuario = Usuario(nome=nome, device_token=token)
    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({
        'id_usuario': novo_usuario.id_usuario,
        'nome': novo_usuario.nome,
        'device_token': novo_usuario.device_token
    }), 201
