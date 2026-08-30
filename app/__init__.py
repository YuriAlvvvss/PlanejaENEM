import logging
import os
import sqlite3
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from flask import Flask, request

from app.extensions import csrf, db, login_manager

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
INSTANCE_DB_PATH = os.path.join(INSTANCE_DIR, "planejaenem.db")


def resolve_database_uri():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return f"sqlite:///{INSTANCE_DB_PATH}"

    normalized_url = database_url.strip()
    if normalized_url.startswith("sqlite:////app/"):
        relative_path = normalized_url.replace("sqlite:////app/", "", 1)
        local_path = os.path.join(BASE_DIR, relative_path)
        return f"sqlite:///{local_path.replace('\\', '/')}"

    return normalized_url


class Config:
    env_name = (os.environ.get("FLASK_ENV") or "development").lower()
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-fallback-key"
    SQLALCHEMY_DATABASE_URI = resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_TIME_LIMIT = 3600
    JSON_SORT_KEYS = False
    PREFERRED_URL_SCHEME = "https" if env_name == "production" else "http"


def build_config(config_name=None):
    env_name = (os.environ.get("FLASK_ENV") or "development").lower()
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if env_name == "production":
            raise RuntimeError("SECRET_KEY is required when FLASK_ENV is set to production.")
        secret_key = "dev-fallback-key"

    config = {
        "SECRET_KEY": secret_key,
        "SQLALCHEMY_DATABASE_URI": resolve_database_uri(),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": env_name == "production" or os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes", "on"},
        "REMEMBER_COOKIE_SECURE": env_name == "production" or os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes", "on"},
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(minutes=30),
        "SESSION_REFRESH_EACH_REQUEST": True,
        "WTF_CSRF_TIME_LIMIT": 3600,
        "JSON_SORT_KEYS": False,
        "PREFERRED_URL_SCHEME": "https" if env_name == "production" else "http",
    }

    if config_name == "testing":
        config.update({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        })

    return config


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


def _sqlite_columns(connection, table_name):
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _add_missing_column(connection, table_name, column_name, ddl):
    columns = _sqlite_columns(connection, table_name)
    if not columns or column_name in columns:
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def migrate_legacy_database(app):
    """Add missing columns to SQLite databases created before schema evolution."""
    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not database_uri.startswith("sqlite") or database_uri.endswith(":memory:"):
        return

    db_path = database_uri.replace("sqlite:///", "", 1)
    if not db_path or not os.path.exists(db_path):
        return

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "subjects" in tables:
            _add_missing_column(
                connection, "subjects", "prioridade", "prioridade INTEGER NOT NULL DEFAULT 3"
            )
            _add_missing_column(
                connection, "subjects", "dificuldade", "dificuldade INTEGER NOT NULL DEFAULT 3"
            )
            _add_missing_column(
                connection, "subjects", "area", "area VARCHAR(20) NOT NULL DEFAULT 'outro'"
            )
        if "users" in tables:
            _add_missing_column(
                connection,
                "users",
                "weekly_goal_minutes",
                "weekly_goal_minutes INTEGER NOT NULL DEFAULT 600",
            )
        if "tasks" in tables:
            _add_missing_column(connection, "tasks", "completed_at", "completed_at DATETIME")
            _add_missing_column(connection, "tasks", "next_review_date", "next_review_date DATE")
        if "study_sessions" in tables:
            _add_missing_column(
                connection,
                "study_sessions",
                "completed",
                "completed BOOLEAN NOT NULL DEFAULT 0",
            )
            _add_missing_column(
                connection, "study_sessions", "completed_at", "completed_at DATETIME"
            )
            _add_missing_column(
                connection, "study_sessions", "session_type",
                "session_type VARCHAR(20) NOT NULL DEFAULT 'teoria'",
            )
        connection.commit()


def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_mapping(build_config(config_name))

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar esta página."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    setup_logging(app)

    @app.before_request
    def log_request_info():
        if not app.config.get("TESTING"):
            app.logger.debug(f"{request.method} {request.path} - IP: {request.remote_addr}")

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        if not app.config.get("TESTING") and request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        else:
            response.headers["Strict-Transport-Security"] = "max-age=0"
        return response

    from app.auth import auth_bp
    from app.main import main_bp
    from app.planner import planner_bp
    from app.subjects import subjects_bp
    from app.tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(subjects_bp, url_prefix="/subjects")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")
    app.register_blueprint(planner_bp)

    with app.app_context():
        from app import models  # noqa: F401
        database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if database_uri.startswith("sqlite") and not database_uri.endswith(":memory:"):
            db_path = database_uri.replace("sqlite:///", "", 1)
            if db_path and db_path != ":memory:":
                db_dir = os.path.dirname(db_path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
        migrate_legacy_database(app)
        db.create_all()

    return app


def setup_logging(app):
    """Configure application logging without creating files in the repository root."""
    if app.config.get("TESTING"):
        return

    log_dir = os.path.join(app.instance_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "planejaenem.log")

    app.logger.propagate = False
    app.logger.setLevel(logging.INFO)

    existing_file_paths = {
        getattr(handler, "baseFilename", None)
        for handler in app.logger.handlers
        if hasattr(handler, "baseFilename")
    }
    if log_path not in existing_file_paths:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10485760,
            backupCount=10,
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

    has_console_handler = any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, RotatingFileHandler)
        for handler in app.logger.handlers
    )
    if not has_console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        console_handler.setLevel(logging.WARNING)
        app.logger.addHandler(console_handler)

    app.logger.info("Application started")

