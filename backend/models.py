from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# User Model
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    preferences = db.relationship('UserPreference', backref='user', lazy=True)
    reading_history = db.relationship('ReadingHistory', backref='user', lazy=True)
    interactions = db.relationship('UserInteraction', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.email}>'

# Article Model
class Article(db.Model):
    __tablename__ = 'articles'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    tags = db.Column(db.String(500))  # comma-separated
    source = db.Column(db.String(200))
    author = db.Column(db.String(200))
    published_date = db.Column(db.DateTime, default=datetime.utcnow)
    image_url = db.Column(db.String(500))
    url = db.Column(db.String(500))
    api_source = db.Column(db.String(50), default='local')  # 'local', 'newsapi', 'guardian'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reading_history = db.relationship('ReadingHistory', backref='article', lazy=True)
    interactions = db.relationship('UserInteraction', backref='article', lazy=True)
    
    def __repr__(self):
        return f'<Article {self.title[:50]}>'

# User Preferences Model
class UserPreference(db.Model):
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    categories = db.Column(db.String(500))  # comma-separated
    tags = db.Column(db.String(500))  # comma-separated
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserPreference {self.user_id}>'

# Reading History Model
class ReadingHistory(db.Model):
    __tablename__ = 'reading_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ReadingHistory User:{self.user_id} Article:{self.article_id}>'

# User Interactions Model (likes, bookmarks, shares)
class UserInteraction(db.Model):
    __tablename__ = 'user_interactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    interaction_type = db.Column(db.String(50))  # 'like', 'bookmark', 'share'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserInteraction {self.interaction_type} by User:{self.user_id}>'