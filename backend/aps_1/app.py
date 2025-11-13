from flask import Flask
from flask_cors import CORS
from routes.air_quality import air_quality_bp
from routes.alerts import alerts_bp, init_alerts
from routes.usuarios import usuarios_bp
from models import db
from routes.enderecos import enderecos_bp

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

app.register_blueprint(enderecos_bp)
app.register_blueprint(air_quality_bp)
app.register_blueprint(alerts_bp)
app.register_blueprint(usuarios_bp)

# inicializa DB e scheduler relacionados a alerts (após registrar blueprint)
init_alerts(app)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
