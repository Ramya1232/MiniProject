from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///newsai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    url = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    source = db.Column(db.String(100))
    author = db.Column(db.String(200))
    category = db.Column(db.String(50))
    tags = db.Column(db.String(500))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    interests = db.Column(db.Text)
    preferred_sources = db.Column(db.Text)

class ReadingHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'))
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserInteractions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    article_id = db.Column(db.Integer)
    interaction_type = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize database
with app.app_context():
    print("🔄 Creating database tables...")
    db.drop_all()
    db.create_all()
    print("✅ Created all tables")
    
    # Create admin user
    print("\n🔄 Creating admin user...")
    admin = User(
        email='admin@news.com',
        password=hashlib.sha256('admin123'.encode()).hexdigest(),
        name='Admin User',
        role='admin'
    )
    db.session.add(admin)
    
    # Create sample articles
    print("🔄 Creating sample articles...")
    articles = [
        Article(
            title='AI Revolution in Healthcare',
            description='Artificial intelligence is transforming medical diagnosis and treatment.',
            content='Full content here...',
            category='Technology',
            tags='AI, Healthcare, Technology',
            source='TechNews',
            author='John Doe',
            image_url='https://via.placeholder.com/400x200?text=AI+Healthcare'
        ),
        Article(
            title='Climate Change Solutions',
            description='New renewable energy technologies offering hope for the future.',
            content='Full content here...',
            category='Environment',
            tags='Climate, Environment, Energy',
            source='EcoDaily',
            author='Jane Smith',
            image_url='https://via.placeholder.com/400x200?text=Climate+Solutions'
        ),
        Article(
            title='Stock Market Trends 2025',
            description='Analysis of current market conditions and future predictions.',
            content='Full content here...',
            category='Business',
            tags='Finance, Business, Markets',
            source='FinanceToday',
            author='Mike Johnson',
            image_url='https://via.placeholder.com/400x200?text=Stock+Market'
        )
    ]
    
    for article in articles:
        db.session.add(article)
    
    db.session.commit()
    print("✅ Created admin user and sample articles")
    
    print("\n" + "="*50)
    print("✅ DATABASE INITIALIZATION COMPLETE!")
    print("="*50)
    print("\n📧 Admin Login:")
    print("   Email: admin@news.com")
    print("   Password: admin123")