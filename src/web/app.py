"""
EAS Webapp Flask application
"""

from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__, static_folder='../../static', static_url_path='/static')
    CORS(app)

    # register blueprints
    from .routes import api_bp, views_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(views_bp)

    return app
