from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app import app, db, User, Menfess, Category, Report, Like, Comment

# Initialize Flask-Migrate
migrate = Migrate(app, db)

if __name__ == '__main__':
    print("Run the following commands to update your database:")
    print("flask db init")
    print("flask db migrate -m 'Add profile pictures and comments'")
    print("flask db upgrade")
