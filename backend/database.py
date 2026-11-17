"""
database.py
-----------
Initializes Flask-SQLAlchemy.

Usage in app.py:
    from database import db
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///party.db"
    db.init_app(app)
    with app.app_context():
        db.create_all()
"""

from flask_sqlalchemy import SQLAlchemy

# Single shared db instance imported by both models and app.
db = SQLAlchemy()
