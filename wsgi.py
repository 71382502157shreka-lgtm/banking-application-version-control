"""
WSGI application entry point for production deployments (Gunicorn / Waitress / uWSGI).
"""
import os
from app import create_app

env = os.environ.get("FLASK_ENV", "production")
app = create_app(env)

if __name__ == "__main__":
    app.run()
