import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fallback-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///planejaenem.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_TIME_LIMIT = 3600
    # Additional security settings
    JSON_SORT_KEYS = False
    PREFERRED_URL_SCHEME = "https" if os.environ.get("FLASK_ENV") == "production" else "http"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_name == "testing":
        app.config.from_object(TestingConfig)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar esta página."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    # Setup logging
    setup_logging(app)

    # Request logging middleware
    @app.before_request
    def log_request_info():
        if not app.config.get("TESTING"):
            app.logger.debug(f"{request.method} {request.path} - IP: {request.remote_addr}")

    # Enhanced security headers
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response

    from app.auth import auth_bp
    from app.main import main_bp
    from app.subjects import subjects_bp
    from app.tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(subjects_bp, url_prefix="/subjects")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return app


def setup_logging(app):
    """Configure application logging"""
    if not app.config.get("TESTING"):
        # Create logs directory if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")

        # File handler with rotation
        file_handler = RotatingFileHandler(
            "logs/planejaenem.log",
            maxBytes=10485760,  # 10 MB
            backupCount=10,
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        console_handler.setLevel(logging.WARNING)

        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Application started")

