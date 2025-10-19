from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import jwt
from functools import wraps
import hashlib
import os
import requests
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///newsai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)
db = SQLAlchemy(app)

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
GUARDIAN_API_KEY = os.getenv('GUARDIAN_API_KEY')

print(f"✅ NewsAPI Key loaded: {NEWS_API_KEY[:20]}..." if NEWS_API_KEY else "❌ NEWS_API_KEY not found in .env")
print(f"✅ Guardian Key loaded: {GUARDIAN_API_KEY[:20]}..." if GUARDIAN_API_KEY else "❌ GUARDIAN_API_KEY not found in .env")

# ========================================
# NLP FEATURE 1: SYNONYM DICTIONARY
# ========================================
SYNONYMS = {
    'tech': ['technology', 'technical', 'digital', 'IT', 'computing'],
    'technology': ['tech', 'digital', 'IT', 'computing', 'innovation'],
    'phone': ['mobile', 'smartphone', 'cellphone', 'device', 'iPhone', 'Android'],
    'mobile': ['phone', 'smartphone', 'cellphone', 'device'],
    'ai': ['artificial intelligence', 'machine learning', 'ML', 'deep learning', 'neural network'],
    'artificial intelligence': ['AI', 'machine learning', 'ML', 'deep learning'],
    'ml': ['machine learning', 'AI', 'artificial intelligence'],
    'car': ['automobile', 'vehicle', 'auto', 'motor'],
    'vehicle': ['car', 'automobile', 'auto', 'motor', 'transport'],
    'computer': ['PC', 'laptop', 'desktop', 'machine', 'system'],
    'laptop': ['notebook', 'computer', 'portable computer'],
    'news': ['article', 'story', 'report', 'update', 'information'],
    'business': ['economy', 'finance', 'trade', 'commerce', 'market'],
    'health': ['medical', 'healthcare', 'wellness', 'medicine', 'fitness'],
    'sport': ['sports', 'athletic', 'game', 'match', 'tournament'],
    'sports': ['sport', 'athletic', 'game', 'match', 'tournament'],
    'politics': ['political', 'government', 'policy', 'election', 'parliament'],
    'environment': ['environmental', 'climate', 'nature', 'ecology', 'green'],
    'science': ['scientific', 'research', 'study', 'experiment', 'discovery'],
}

# ========================================
# NLP FEATURE 2: QUERY EXPANSION
# ========================================
def expand_search_query(query):
    """
    Expands search query with synonyms for better results
    Example: 'tech news' -> 'tech technology digital IT news article story'
    """
    if not query:
        return query
    
    query = query.lower().strip()
    words = re.findall(r'\w+', query)  # Extract words
    
    expanded_words = set()
    for word in words:
        expanded_words.add(word)
        # Add synonyms if available
        if word in SYNONYMS:
            expanded_words.update(SYNONYMS[word][:3])  # Add top 3 synonyms
    
    expanded_query = ' '.join(expanded_words)
    print(f"🔍 NLP Query Expansion: '{query}' -> '{expanded_query}'")
    return expanded_query

# ========================================
# NLP FEATURE 3: SMART SEARCH SCORING
# ========================================
def calculate_relevance_score(article, search_terms):
    """
    Calculate relevance score based on keyword matches
    Higher score = more relevant article
    """
    score = 0
    search_terms_lower = [term.lower() for term in search_terms]
    
    title = (article.get('title') or '').lower()
    description = (article.get('description') or '').lower()
    content = (article.get('content') or '').lower()
    
    for term in search_terms_lower:
        # Title matches are worth more
        if term in title:
            score += 5
        if term in description:
            score += 2
        if term in content:
            score += 1
    
    return score

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

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

def fetch_from_newsapi(query='news', category=None, page_size=50):
    """Fetch articles from NewsAPI with NLP-enhanced query"""
    if not NEWS_API_KEY:
        print("❌ NewsAPI Key not configured")
        return []
    
    try:
        # NLP Enhancement: Expand query with synonyms
        expanded_query = expand_search_query(query)
        
        url = 'https://newsapi.org/v2/everything'
        params = {
            'apiKey': NEWS_API_KEY,
            'q': expanded_query,  # Use expanded query
            'pageSize': page_size,
            'language': 'en',
            'sortBy': 'publishedAt'
        }
        
        print(f"📡 NewsAPI requesting with NLP: '{query}' (expanded: '{expanded_query}')")
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            print(f"✅ NewsAPI returned {len(articles)} articles")
            
            default_images = {
                'technology': 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&h=200&fit=crop',
                'health': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=400&h=200&fit=crop',
                'business': 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=400&h=200&fit=crop',
                'science': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=200&fit=crop',
                'sports': 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=400&h=200&fit=crop',
                'politics': 'https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=400&h=200&fit=crop',
                'entertainment': 'https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=400&h=200&fit=crop',
                'default': 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=400&h=200&fit=crop'
            }
            
            formatted_articles = []
            search_terms = expanded_query.split()
            
            for article in articles:
                if article.get('title') and article['title'] != '[Removed]':
                    cat_lower = (category or 'general').lower()
                    default_img = default_images.get(cat_lower, default_images['default'])
                    
                    article_data = {
                        'title': article.get('title', 'No Title'),
                        'description': article.get('description', ''),
                        'content': article.get('content', ''),
                        'url': article.get('url', ''),
                        'image_url': article.get('urlToImage') or default_img,
                        'source': article.get('source', {}).get('name', 'NewsAPI'),
                        'author': article.get('author', 'Unknown'),
                        'category': category or 'General',
                        'tags': query,
                        'published_at': article.get('publishedAt', datetime.utcnow().isoformat())
                    }
                    
                    # NLP Enhancement: Calculate relevance score
                    article_data['relevance_score'] = calculate_relevance_score(article_data, search_terms)
                    formatted_articles.append(article_data)
            
            # NLP Enhancement: Sort by relevance score
            formatted_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            print(f"🎯 NLP Ranking: Top article score = {formatted_articles[0].get('relevance_score', 0) if formatted_articles else 0}")
            
            return formatted_articles
        else:
            print(f"❌ NewsAPI Error: Status {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ NewsAPI Exception: {str(e)}")
        return []

def fetch_from_guardian(query='news', page_size=20):
    """Fetch articles from Guardian API with NLP enhancement"""
    if not GUARDIAN_API_KEY:
        return []
    
    try:
        # NLP Enhancement: Expand query
        expanded_query = expand_search_query(query)
        
        url = 'https://content.guardianapis.com/search'
        params = {
            'api-key': GUARDIAN_API_KEY,
            'q': expanded_query,
            'page-size': page_size,
            'show-fields': 'thumbnail,trailText,bodyText'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('response', {}).get('results', [])
            
            formatted_articles = []
            for article in articles:
                fields = article.get('fields', {})
                formatted_articles.append({
                    'title': article.get('webTitle', 'No Title'),
                    'description': fields.get('trailText', ''),
                    'content': fields.get('bodyText', ''),
                    'url': article.get('webUrl', ''),
                    'image_url': fields.get('thumbnail') or 'https://via.placeholder.com/400x200?text=News+Article',
                    'source': 'The Guardian',
                    'author': 'Guardian Staff',
                    'category': article.get('sectionName', 'General'),
                    'tags': query,
                    'published_at': article.get('webPublicationDate', datetime.utcnow().isoformat())
                })
            
            return formatted_articles
        return []
    except Exception as e:
        print(f"❌ Guardian API Exception: {str(e)}")
        return []

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    hashed_password = hashlib.sha256(data['password'].encode()).hexdigest()
    
    new_user = User(
        email=data['email'],
        password=hashed_password,
        name=data.get('name', ''),
        role='user'
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except:
        return jsonify({'message': 'User already exists'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    
    if user and user.password == hashlib.sha256(data['password'].encode()).hexdigest():
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=1)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
        })
    
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/articles', methods=['GET'])
@token_required
def get_articles(current_user):
    """Get articles with NLP-enhanced search"""
    try:
        category = request.args.get('category', '')
        search = request.args.get('search', '')
        fetch_live = request.args.get('fetch_live', 'false').lower() == 'true'
        
        print(f"\n📥 Request: category={category}, search={search}, live={fetch_live}")
        
        if fetch_live:
            print("🔴 Fetching live news with NLP enhancement...")
            
            query = search if search else (category if category else 'news')
            
            articles = []
            newsapi_articles = fetch_from_newsapi(query)
            articles.extend(newsapi_articles)
            
            guardian_articles = fetch_from_guardian(query)
            articles.extend(guardian_articles)
            
            print(f"✅ Total live articles with NLP ranking: {len(articles)}")
            return jsonify(articles)
        
        query_obj = Article.query
        
        if category and category != 'All':
            query_obj = query_obj.filter(Article.category == category)
        
        if search:
            # NLP Enhancement: Expand search query for database search too
            expanded = expand_search_query(search)
            search_terms = expanded.split()
            
            filters = []
            for term in search_terms[:5]:  # Limit to 5 terms
                filters.append(Article.title.contains(term))
                filters.append(Article.description.contains(term))
                filters.append(Article.tags.contains(term))
            
            from sqlalchemy import or_
            query_obj = query_obj.filter(or_(*filters))
        
        articles = query_obj.order_by(Article.published_at.desc()).limit(50).all()
        
        return jsonify([{
            'id': a.id,
            'title': a.title,
            'description': a.description,
            'content': a.content,
            'url': a.url,
            'image_url': a.image_url,
            'source': a.source,
            'author': a.author,
            'category': a.category,
            'tags': a.tags,
            'published_at': a.published_at.isoformat() if a.published_at else None
        } for a in articles])
    
    except Exception as e:
        print(f"❌ Error in get_articles: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/preferences', methods=['GET', 'POST'])
@token_required
def preferences(current_user):
    if request.method == 'GET':
        prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
        if prefs:
            return jsonify({
                'interests': prefs.interests.split(',') if prefs.interests else [],
                'preferred_sources': prefs.preferred_sources.split(',') if prefs.preferred_sources else []
            })
        return jsonify({'interests': [], 'preferred_sources': []})
    
    data = request.json
    prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
    
    if prefs:
        prefs.interests = ','.join(data.get('interests', []))
        prefs.preferred_sources = ','.join(data.get('preferred_sources', []))
    else:
        prefs = UserPreferences(
            user_id=current_user.id,
            interests=','.join(data.get('interests', [])),
            preferred_sources=','.join(data.get('preferred_sources', []))
        )
        db.session.add(prefs)
    
    db.session.commit()
    return jsonify({'message': 'Preferences updated'})

@app.route('/api/interactions', methods=['POST'])
@token_required
def add_interaction(current_user):
    """Fixed: Handle interactions for both database and live news articles"""
    try:
        data = request.json
        print(f"📥 Received interaction data: {data}")
        
        article_id = data.get('article_id') or data.get('id') or 0
        interaction_type = data.get('type', 'like')
        
        interaction = UserInteractions(
            user_id=current_user.id,
            article_id=article_id,
            interaction_type=interaction_type
        )
        
        db.session.add(interaction)
        db.session.commit()
        
        print(f"✅ Interaction saved: user_id={current_user.id}, article_id={article_id}, type={interaction_type}")
        
        return jsonify({
            'message': 'Interaction recorded successfully',
            'success': True,
            'interaction': {
                'user_id': current_user.id,
                'article_id': article_id,
                'type': interaction_type
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Error recording interaction: {str(e)}")
        return jsonify({'message': 'Error recording interaction', 'error': str(e)}), 500

@app.route('/api/admin/articles', methods=['GET', 'POST', 'PUT', 'DELETE'])
@token_required
def admin_articles(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    if request.method == 'GET':
        articles = Article.query.order_by(Article.created_at.desc()).all()
        return jsonify([{
            'id': a.id,
            'title': a.title,
            'description': a.description,
            'content': a.content,
            'category': a.category,
            'tags': a.tags,
            'source': a.source,
            'author': a.author,
            'image_url': a.image_url,
            'published_at': a.published_at.isoformat() if a.published_at else None
        } for a in articles])
    
    elif request.method == 'POST':
        data = request.json
        article = Article(
            title=data['title'],
            description=data.get('description', ''),
            content=data.get('content', ''),
            category=data.get('category', 'General'),
            tags=data.get('tags', ''),
            source=data.get('source', 'Admin'),
            author=data.get('author', current_user.name),
            image_url=data.get('image_url', '')
        )
        db.session.add(article)
        db.session.commit()
        return jsonify({'message': 'Article created', 'id': article.id}), 201
    
    elif request.method == 'PUT':
        data = request.json
        article = Article.query.get(data['id'])
        if article:
            article.title = data.get('title', article.title)
            article.description = data.get('description', article.description)
            article.content = data.get('content', article.content)
            article.category = data.get('category', article.category)
            article.tags = data.get('tags', article.tags)
            article.source = data.get('source', article.source)
            article.author = data.get('author', article.author)
            article.image_url = data.get('image_url', article.image_url)
            db.session.commit()
            return jsonify({'message': 'Article updated'})
        return jsonify({'message': 'Article not found'}), 404
    
    elif request.method == 'DELETE':
        article_id = request.args.get('id')
        article = Article.query.get(article_id)
        if article:
            db.session.delete(article)
            db.session.commit()
            return jsonify({'message': 'Article deleted'})
        return jsonify({'message': 'Article not found'}), 404

@app.route('/api/admin/users', methods=['GET'])
@token_required
def admin_users(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role,
        'created_at': u.created_at.isoformat()
    } for u in users])

@app.route('/api/admin/stats', methods=['GET'])
@token_required
def admin_stats(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    return jsonify({
        'total_users': User.query.count(),
        'total_articles': Article.query.count(),
        'total_reads': ReadingHistory.query.count(),
        'total_interactions': UserInteractions.query.count()
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database tables ready")
        
        admin = User.query.filter_by(email='admin@news.com').first()
        if not admin:
            admin = User(
                email='admin@news.com',
                password=hashlib.sha256('admin123'.encode()).hexdigest(),
                name='Admin User',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created: admin@news.com / admin123")
        
    print("\n🚀 Starting NewsAI backend with NLP features...")
    print("🤖 NLP Features Enabled:")
    print("   ✅ Synonym expansion (tech → technology, digital, IT)")
    print("   ✅ Smart query expansion")
    print("   ✅ Relevance scoring and ranking")
    print("📡 Make sure your .env file has valid API keys!")
    app.run(debug=True, port=5000)