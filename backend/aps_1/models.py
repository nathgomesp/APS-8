from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    device_token = db.Column(db.String(255), nullable=True)
    nome = db.Column(db.String(100), nullable=True)

class Localizacao(db.Model):
    __tablename__ = 'localizacoes'
    id_localizacao = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    nome_local = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    aqi_limite = db.Column(db.Integer, nullable=False)

class Alerta(db.Model):
    __tablename__ = 'alertas'
    id_alerta = db.Column(db.Integer, primary_key=True)
    id_localizacao = db.Column(db.Integer, db.ForeignKey('localizacoes.id_localizacao'), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    aqi_registrado = db.Column(db.Integer, nullable=False)
    mensagem = db.Column(db.String(255), nullable=False)
