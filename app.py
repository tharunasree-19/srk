from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError, NoCredentialsError
import uuid
from datetime import datetime
from decimal import Decimal
import os
from dotenv import load_dotenv
import secrets

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

print("\n" + "="*80)
print("🎬 CinemaPulse - Real-Time Movie Feedback & Analytics Platform")
print("="*80)

# ============================================================================
# AWS DYNAMODB CONFIGURATION
# ============================================================================

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
aws_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')

print(f"📍 Region: {AWS_REGION}")

use_dynamodb = False
dynamodb = None
users_table = None
reviews_table = None
movies_table = None

# Try to connect to DynamoDB (supports both credentials and IAM roles)
try:
    # Try IAM role first (recommended for EC2/Lambda)
    if not aws_key or not aws_secret:
        print("🔐 Attempting to use IAM role credentials...")
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    else:
        print("🔐 Using explicit AWS credentials...")
        print(f"🔑 Access Key: {aws_key[:10] + '...' if aws_key else '❌ NOT SET'}")
        dynamodb = boto3.resource('dynamodb', 
                                 region_name=AWS_REGION,
                                 aws_access_key_id=aws_key,
                                 aws_secret_access_key=aws_secret)
    
    # Test connection
    dynamodb.meta.client.list_tables()
    print("✅ Connected to AWS DynamoDB successfully!")
    use_dynamodb = True
    
except NoCredentialsError:
    print("⚠️  No AWS credentials found")
    print("⚠️  Running in IN-MEMORY MODE")
    use_dynamodb = False
except Exception as e:
    print(f"⚠️  AWS Connection Failed: {e}")
    print("⚠️  Running in IN-MEMORY MODE")
    use_dynamodb = False

print("="*80 + "\n")

# ============================================================================
# IN-MEMORY STORAGE (FALLBACK)
# ============================================================================

IN_MEMORY_REVIEWS = []
IN_MEMORY_USERS = {}

# ============================================================================
# MOVIES DATABASE
# ============================================================================

MOVIES = [
    {
        'movie_id': 'movie_001',
        'title': 'The Quantum Paradox',
        'description': 'A mind-bending sci-fi thriller exploring parallel universes and quantum mechanics.',
        'genre': 'Sci-Fi',
        'release_year': 2024,
        'director': 'Sarah Mitchell',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg',
        'active': True
    },
    {
        'movie_id': 'movie_002',
        'title': 'Echoes of Tomorrow',
        'description': 'A heartwarming drama about family, time travel, and second chances.',
        'genre': 'Drama',
        'release_year': 2025,
        'director': 'James Chen',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/kXfqcdQKsToO0OUXHcrrNCHDBzO.jpg',
        'active': True
    },
    {
        'movie_id': 'movie_003',
        'title': 'Shadow Protocol',
        'description': 'An action-packed espionage thriller with explosive sequences and plot twists.',
        'genre': 'Action',
        'release_year': 2025,
        'director': 'Marcus Rodriguez',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/7WsyChQLEftFiDOVTGkv3hFpyyt.jpg',
        'active': True
    },
    {
        'movie_id': 'movie_004',
        'title': 'The Last Symphony',
        'description': 'A biographical drama about a legendary composer\'s final masterpiece.',
        'genre': 'Drama',
        'release_year': 2024,
        'director': 'Elena Volkov',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/qNBAXBIQlnOThrVvA6mA2B5ggV6.jpg',
        'active': True
    },
    {
        'movie_id': 'movie_005',
        'title': 'Neon City',
        'description': 'A cyberpunk adventure set in a dystopian future with stunning visuals.',
        'genre': 'Sci-Fi',
        'release_year': 2026,
        'director': 'Kenji Tanaka',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/pwGmXVKUgKN13psUjlhC9zBcq1o.jpg',
        'active': True
    },
    {
        'movie_id': 'movie_006',
        'title': 'Desert Storm',
        'description': 'A survival thriller about a group stranded in the Sahara Desert.',
        'genre': 'Thriller',
        'release_year': 2025,
        'director': 'Ahmed Hassan',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/9BBTo63ANSmhC4e6r62OJFuK2GL.jpg',
        'active': True
    },
    {
        'movie_id': 'movie_007',
        'title': 'Midnight Racing',
        'description': 'Underground street racing meets high-stakes heist in this adrenaline rush.',
        'genre': 'Action',
        'release_year': 2025,
        'director': 'Lucas Knight',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/sv1xJUazXeYqALyczSZ3O6nkH75.jpg',
        'active': True
    },
    {
        'movie_id': 'movie_008',
        'title': 'The Forgotten Island',
        'description': 'Archaeologists discover a mysterious civilization on a remote island.',
        'genre': 'Adventure',
        'release_year': 2024,
        'director': 'Isabella Santos',
        'total_reviews': 0,
        'avg_rating': 0.0,
        'image_url': 'https://image.tmdb.org/t/p/w500/yDHYTfA3R0jFYba16jBB1ef8oIt.jpg',
        'active': True
    }
]

print(f"✅ Loaded {len(MOVIES)} movies into memory\n")

# ============================================================================
# DYNAMODB TABLE INITIALIZATION
# ============================================================================

def create_dynamodb_tables():
    """Create DynamoDB tables if they don't exist"""
    if not use_dynamodb:
        return False
        
    try:
        existing_tables = dynamodb.meta.client.list_tables()['TableNames']
        print(f"📋 Existing DynamoDB tables: {existing_tables}")
        
        # Users Table
        USERS_TABLE_NAME = 'CinemaPulse_Users'
        if USERS_TABLE_NAME not in existing_tables:
            print(f"🔨 Creating {USERS_TABLE_NAME} table...")
            table = dynamodb.create_table(
                TableName=USERS_TABLE_NAME,
                KeySchema=[
                    {'AttributeName': 'email', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'email', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[{'Key': 'Application', 'Value': 'CinemaPulse'}]
            )
            table.wait_until_exists()
            print(f"✅ {USERS_TABLE_NAME} created!")
        else:
            print(f"✅ {USERS_TABLE_NAME} exists")
        
        # Reviews Table with GSI
        REVIEWS_TABLE_NAME = 'CinemaPulse_Reviews'
        if REVIEWS_TABLE_NAME not in existing_tables:
            print(f"🔨 Creating {REVIEWS_TABLE_NAME} table...")
            table = dynamodb.create_table(
                TableName=REVIEWS_TABLE_NAME,
                KeySchema=[
                    {'AttributeName': 'user_email', 'KeyType': 'HASH'},
                    {'AttributeName': 'review_id', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'user_email', 'AttributeType': 'S'},
                    {'AttributeName': 'review_id', 'AttributeType': 'S'},
                    {'AttributeName': 'movie_id', 'AttributeType': 'S'},
                    {'AttributeName': 'created_at', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'MovieIndex',
                        'KeySchema': [
                            {'AttributeName': 'movie_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[{'Key': 'Application', 'Value': 'CinemaPulse'}]
            )
            table.wait_until_exists()
            print(f"✅ {REVIEWS_TABLE_NAME} created!")
        else:
            print(f"✅ {REVIEWS_TABLE_NAME} exists")
        
        # Movies Table
        MOVIES_TABLE_NAME = 'CinemaPulse_Movies'
        if MOVIES_TABLE_NAME not in existing_tables:
            print(f"🔨 Creating {MOVIES_TABLE_NAME} table...")
            table = dynamodb.create_table(
                TableName=MOVIES_TABLE_NAME,
                KeySchema=[
                    {'AttributeName': 'movie_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'movie_id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[{'Key': 'Application', 'Value': 'CinemaPulse'}]
            )
            table.wait_until_exists()
            print(f"✅ {MOVIES_TABLE_NAME} created!")
        else:
            print(f"✅ {MOVIES_TABLE_NAME} exists")
        
        print("\n✅ All DynamoDB tables ready!\n")
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

# Initialize tables
if use_dynamodb:
    create_dynamodb_tables()
    users_table = dynamodb.Table('CinemaPulse_Users')
    reviews_table = dynamodb.Table('CinemaPulse_Reviews')
    movies_table = dynamodb.Table('CinemaPulse_Movies')
    
    # Initialize movies in DynamoDB
    print("📽️  Initializing movies in DynamoDB...")
    for movie in MOVIES:
        try:
            movies_table.put_item(
                Item={
                    'movie_id': movie['movie_id'],
                    'title': movie['title'],
                    'description': movie['description'],
                    'genre': movie['genre'],
                    'release_year': movie['release_year'],
                    'director': movie['director'],
                    'image_url': movie['image_url'],
                    'total_reviews': 0,
                    'avg_rating': Decimal('0.0'),
                    'active': True,
                    'last_updated': datetime.now().isoformat()
                },
                ConditionExpression='attribute_not_exists(movie_id)'  # Only create if doesn't exist
            )
            print(f"  ✅ Created movie: {movie['title']}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                pass  # Movie already exists, skip
            else:
                print(f"  ⚠️  Error with {movie['title']}: {e}")
    print("✅ Movies initialized!\n")

# ============================================================================
# HELPER FUNCTIONS - DYNAMODB
# ============================================================================

def save_review_to_dynamodb(name, email, movie_id, rating, feedback_text):
    """Save review to DynamoDB"""
    try:
        timestamp = datetime.now().isoformat()
        review_id = f"{movie_id}#{timestamp}"
        
        # Save review
        reviews_table.put_item(Item={
            'user_email': email,
            'review_id': review_id,
            'movie_id': movie_id,
            'rating': rating,
            'feedback': feedback_text,
            'name': name,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'timestamp': timestamp
        })
        
        # Update or create user
        try:
            user_response = users_table.get_item(Key={'email': email})
            if 'Item' in user_response:
                user = user_response['Item']
                total_reviews = user.get('total_reviews', 0) + 1
                old_avg = float(user.get('avg_rating', 0))
                new_avg = ((old_avg * (total_reviews - 1)) + rating) / total_reviews
                
                users_table.update_item(
                    Key={'email': email},
                    UpdateExpression='SET total_reviews = :tr, avg_rating = :ar, last_review_date = :lrd, #n = :name',
                    ExpressionAttributeNames={'#n': 'name'},
                    ExpressionAttributeValues={
                        ':tr': total_reviews,
                        ':ar': Decimal(str(new_avg)),
                        ':lrd': datetime.now().strftime("%Y-%m-%d"),
                        ':name': name
                    }
                )
            else:
                users_table.put_item(Item={
                    'email': email,
                    'name': name,
                    'created_at': timestamp,
                    'total_reviews': 1,
                    'avg_rating': Decimal(str(rating)),
                    'last_review_date': datetime.now().strftime("%Y-%m-%d")
                })
        except Exception as e:
            print(f"⚠️  Error updating user: {e}")
        
        # Update movie statistics
        try:
            movie_reviews = reviews_table.query(
                IndexName='MovieIndex',
                KeyConditionExpression=Key('movie_id').eq(movie_id)
            )
            
            reviews_list = movie_reviews.get('Items', [])
            total_reviews = len(reviews_list)
            avg_rating = sum(r['rating'] for r in reviews_list) / total_reviews if total_reviews > 0 else 0
            
            movies_table.update_item(
                Key={'movie_id': movie_id},
                UpdateExpression='SET total_reviews = :tr, avg_rating = :ar, last_updated = :lu',
                ExpressionAttributeValues={
                    ':tr': total_reviews,
                    ':ar': Decimal(str(avg_rating)),
                    ':lu': timestamp
                }
            )
        except Exception as e:
            print(f"⚠️  Error updating movie stats: {e}")
        
        print(f"✅ Review saved to DynamoDB by {name} ({email})")
        return True
        
    except Exception as e:
        print(f"❌ Error saving to DynamoDB: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_reviews_from_dynamodb(movie_id, limit=20):
    """Get all reviews for a movie from DynamoDB"""
    try:
        response = reviews_table.query(
            IndexName='MovieIndex',
            KeyConditionExpression=Key('movie_id').eq(movie_id),
            ScanIndexForward=False,
            Limit=limit
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"❌ Error getting reviews: {e}")
        return []

def get_user_reviews_from_dynamodb(email):
    """Get all reviews by user from DynamoDB"""
    try:
        response = reviews_table.query(
            KeyConditionExpression=Key('user_email').eq(email)
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"❌ Error getting user reviews: {e}")
        return []

def get_user_from_dynamodb(email):
    """Get user info from DynamoDB"""
    try:
        response = users_table.get_item(Key={'email': email})
        return response.get('Item')
    except Exception as e:
        print(f"❌ Error getting user: {e}")
        return None

def get_movies_from_dynamodb():
    """Get all movies from DynamoDB"""
    try:
        response = movies_table.scan()
        movies = response.get('Items', [])
        
        for movie in movies:
            movie['avg_rating'] = float(movie.get('avg_rating', 0))
            movie['total_reviews'] = int(movie.get('total_reviews', 0))
        
        return movies
    except Exception as e:
        print(f"❌ Error getting movies: {e}")
        return MOVIES

# ============================================================================
# HELPER FUNCTIONS - IN-MEMORY (FALLBACK)
# ============================================================================

def save_review_to_memory(name, email, movie_id, rating, feedback_text):
    """Save review to in-memory storage"""
    review = {
        'review_id': str(uuid.uuid4()),
        'name': name,
        'email': email,
        'movie_id': movie_id,
        'rating': int(rating),
        'feedback': feedback_text,
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'timestamp': datetime.now().isoformat()
    }
    IN_MEMORY_REVIEWS.append(review)
    
    if email not in IN_MEMORY_USERS:
        IN_MEMORY_USERS[email] = {
            'name': name,
            'email': email,
            'total_reviews': 0,
            'avg_rating': 0.0
        }
    
    user_reviews = [r for r in IN_MEMORY_REVIEWS if r['email'] == email]
    IN_MEMORY_USERS[email]['total_reviews'] = len(user_reviews)
    IN_MEMORY_USERS[email]['avg_rating'] = sum(r['rating'] for r in user_reviews) / len(user_reviews)
    
    print(f"✅ Review saved to memory by {name} ({email})")
    return True

def get_reviews_from_memory(movie_id, limit=20):
    """Get all reviews for a movie from memory"""
    reviews = [r for r in IN_MEMORY_REVIEWS if r['movie_id'] == str(movie_id)]
    return sorted(reviews, key=lambda x: x['timestamp'], reverse=True)[:limit]

def get_user_reviews_from_memory(email):
    """Get all reviews by user from memory"""
    reviews = [r for r in IN_MEMORY_REVIEWS if r['email'] == email]
    return sorted(reviews, key=lambda x: x['timestamp'], reverse=True)

def get_user_from_memory(email):
    """Get user info from memory"""
    return IN_MEMORY_USERS.get(email)

def get_movies_from_memory():
    """Get all movies with stats from memory"""
    movies = [dict(m) for m in MOVIES if m.get('active', True)]
    for movie in movies:
        movie_reviews = [r for r in IN_MEMORY_REVIEWS if r['movie_id'] == movie['movie_id']]
        movie['total_reviews'] = len(movie_reviews)
        if movie_reviews:
            movie['avg_rating'] = sum(r['rating'] for r in movie_reviews) / len(movie_reviews)
        else:
            movie['avg_rating'] = 0.0
    return movies

# ============================================================================
# UNIFIED HELPER FUNCTIONS
# ============================================================================

def get_all_movies():
    """Retrieve all active movies"""
    if use_dynamodb:
        return get_movies_from_dynamodb()
    else:
        return get_movies_from_memory()

def get_movie_by_id(movie_id):
    """Get specific movie"""
    movies = get_all_movies()
    return next((m for m in movies if m['movie_id'] == str(movie_id)), None)

def submit_review(name, email, movie_id, rating, feedback_text):
    """Submit a movie review"""
    try:
        if use_dynamodb:
            success = save_review_to_dynamodb(name, email, movie_id, rating, feedback_text)
        else:
            success = save_review_to_memory(name, email, movie_id, rating, feedback_text)
        
        if success:
            user_reviews = get_user_reviews(email)
            session['user_total_reviews'] = len(user_reviews)
            session['user_avg_rating'] = sum(r['rating'] for r in user_reviews) / len(user_reviews)
        
        return success
    except Exception as e:
        print(f"❌ Error submitting review: {e}")
        return False

def get_movie_reviews(movie_id, limit=20):
    """Get all reviews for a movie"""
    if use_dynamodb:
        return get_reviews_from_dynamodb(movie_id, limit)
    else:
        return get_reviews_from_memory(movie_id, limit)

def get_user_reviews(email):
    """Get all reviews by user email"""
    if use_dynamodb:
        return get_user_reviews_from_dynamodb(email)
    else:
        return get_user_reviews_from_memory(email)

def calculate_user_average(email):
    """Calculate user's average rating"""
    if use_dynamodb:
        user = get_user_from_dynamodb(email)
        if user:
            return float(user.get('avg_rating', 0))
        return 0.0
    else:
        user = get_user_from_memory(email)
        if user:
            return user.get('avg_rating', 0.0)
        return 0.0

def get_recommendations(email, limit=5):
    """Get personalized recommendations"""
    all_movies = get_all_movies()
    user_reviews = get_user_reviews(email)
    
    if not user_reviews:
        return sorted(all_movies, key=lambda x: x.get('avg_rating', 0), reverse=True)[:limit]
    
    genre_prefs = {}
    rated_ids = set()
    
    for review in user_reviews:
        rated_ids.add(review['movie_id'])
        rating = review.get('rating', 0)
        
        movie = next((m for m in all_movies if m['movie_id'] == review['movie_id']), None)
        if movie:
            genre = movie['genre']
            if genre not in genre_prefs:
                genre_prefs[genre] = []
            genre_prefs[genre].append(rating)
    
    fav_genres = [g for g, ratings in genre_prefs.items() if sum(ratings)/len(ratings) >= 4]
    
    recommendations = [m for m in all_movies if m['movie_id'] not in rated_ids and m['genre'] in fav_genres]
    recommendations.sort(key=lambda x: x.get('avg_rating', 0), reverse=True)
    
    if len(recommendations) < limit:
        other = [m for m in all_movies if m['movie_id'] not in rated_ids and m not in recommendations]
        other.sort(key=lambda x: x.get('avg_rating', 0), reverse=True)
        recommendations.extend(other[:limit - len(recommendations)])
    
    return recommendations[:limit]

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Home page"""
    return render_template('home.html')

@app.route('/movies')
def movies():
    """Movies listing"""
    all_movies = get_all_movies()
    genre_filter = request.args.get('genre', 'all').lower()
    
    if genre_filter != 'all':
        all_movies = [m for m in all_movies if m.get('genre', '').lower() == genre_filter]
    
    all_movies.sort(key=lambda x: x.get('avg_rating', 0), reverse=True)
    
    return render_template('movies.html', movies=all_movies, current_genre=genre_filter)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    """Movie detail page"""
    movie = get_movie_by_id(movie_id)
    if not movie:
        flash("Movie not found!", "danger")
        return redirect(url_for('movies'))
    
    reviews = get_movie_reviews(movie_id)
    
    return render_template('movie_detail.html', movie=movie, feedback_list=reviews)

@app.route('/feedback/<movie_id>')
def feedback_page(movie_id):
    """Feedback form"""
    movie = get_movie_by_id(movie_id)
    if not movie:
        flash("Movie not found!", "danger")
        return redirect(url_for('movies'))
    
    return render_template('feedback.html', movie=movie)

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback_route():
    """Submit review"""
    try:
        print("\n" + "="*50)
        print("📝 FORM SUBMISSION RECEIVED")
        print("="*50)
        
        movie_id = request.form.get('movie_id')
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        feedback_text = request.form.get('feedback', '').strip()
        rating_raw = request.form.get('rating', '')
        
        print(f"Movie ID: {movie_id}")
        print(f"Name: {name}")
        print(f"Email: {email}")
        print(f"Rating (raw): '{rating_raw}'")
        print(f"Storage Mode: {'DynamoDB' if use_dynamodb else 'In-Memory'}")
        
        if not movie_id:
            flash('Movie ID is missing!', 'danger')
            return redirect(url_for('movies'))
        
        if not name:
            flash('Name is required!', 'danger')
            return redirect(url_for('feedback_page', movie_id=movie_id))
        
        if not email:
            flash('Email is required!', 'danger')
            return redirect(url_for('feedback_page', movie_id=movie_id))
        
        if not rating_raw or rating_raw == '':
            flash('Please select a rating!', 'danger')
            return redirect(url_for('feedback_page', movie_id=movie_id))
        
        try:
            rating = int(rating_raw)
        except (ValueError, TypeError):
            flash('Invalid rating value!', 'danger')
            return redirect(url_for('feedback_page', movie_id=movie_id))
        
        if rating < 1 or rating > 5:
            flash('Rating must be between 1 and 5!', 'danger')
            return redirect(url_for('feedback_page', movie_id=movie_id))
        
        session['user_name'] = name
        session['user_email'] = email
        
        print(f"\n✅ All validations passed!")
        print(f"Submitting review: {name} rated {rating}/5 for movie {movie_id}")
        
        success = submit_review(name, email, movie_id, rating, feedback_text)
        
        if success:
            print("✅ Review submitted successfully!")
            if use_dynamodb:
                print("💾 Saved to DynamoDB tables!")
            print("="*50 + "\n")
            flash('Thank you for your review!', 'success')
            return redirect(url_for('thankyou', movie_id=movie_id))
        else:
            print("❌ ERROR: submit_review() returned False")
            flash('Failed to submit review. Please try again.', 'danger')
            return redirect(url_for('feedback_page', movie_id=movie_id))
            
    except Exception as e:
        print(f"\n❌ EXCEPTION in submit_feedback_route: {e}")
        import traceback
        traceback.print_exc()
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('movies'))

@app.route('/thankyou')
def thankyou():
    """Thank you page"""
    movie_id = request.args.get('movie_id')
    movie = get_movie_by_id(movie_id) if movie_id else None
    
    user_email = session.get('user_email')
    user_name = session.get('user_name')
    
    if user_email:
        recommendations = get_recommendations(user_email, 4)
        user_avg = calculate_user_average(user_email)
    else:
        recommendations = []
        user_avg = 0.0
    
    return render_template('thankyou.html', 
                         movie=movie,
                         recommendations=recommendations,
                         user_avg_rating=user_avg)

@app.route('/analytics')
@app.route('/analytics')
def analytics():
    """Analytics dashboard"""
    all_movies = get_all_movies()
    
    user_email = session.get('user_email')
    user_name = session.get('user_name')
    
    if user_email:
        user_reviews = get_user_reviews(user_email)
        user_avg = calculate_user_average(user_email)
        recommendations = get_recommendations(user_email, 5)
    else:
        user_reviews = []
        user_avg = 0.0
        recommendations = []
    
    genres = {}
    for m in all_movies:
        genre = m.get('genre', 'Unknown')
        genres[genre] = genres.get(genre, 0) + 1
    
    # Get total reviews count
    if use_dynamodb:
        try:
            response = reviews_table.scan(Select='COUNT')
            total_reviews = response.get('Count', 0)
        except:
            total_reviews = len(user_reviews)
    else:
        total_reviews = len(IN_MEMORY_REVIEWS)
    
    return render_template('analytics.html',
                         total_movies=len(all_movies),
                         total_reviews=total_reviews,
                         top_movies=sorted(all_movies, key=lambda x: x.get('avg_rating', 0), reverse=True)[:10],
                         most_reviewed=sorted(all_movies, key=lambda x: x.get('total_reviews', 0), reverse=True)[:10],
                         genres=genres,
                         recommendations=recommendations,
                         user_name=user_name,
                         user_email=user_email,
                         user_avg_rating=round(user_avg, 2),
                         user_total_reviews=len(user_reviews))

@app.route('/my-reviews')
def my_reviews():
    """User's review history"""
    user_email = session.get('user_email')
    user_name = session.get('user_name')
    
    if not user_email:
        flash('Please submit a review first to see your profile!', 'info')
        return redirect(url_for('movies'))
    
    user_reviews = get_user_reviews(user_email)
    all_movies = get_all_movies()
    
    for review in user_reviews:
        movie = next((m for m in all_movies if m['movie_id'] == review['movie_id']), None)
        if movie:
            review['movie_title'] = movie['title']
            review['movie_genre'] = movie['genre']
            review['movie_image'] = movie['image_url']
    
    recommendations = get_recommendations(user_email, 6)
    avg_rating = calculate_user_average(user_email)
    
    return render_template('my_reviews.html',
                         user_name=user_name,
                         user_email=user_email,
                         user_feedback=user_reviews,
                         recommendations=recommendations,
                         total_reviews=len(user_reviews),
                         avg_user_rating=avg_rating)

@app.route('/favicon.ico')
def favicon():
    return '', 204

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == '__main__':
    print("="*80)
    print("🎬 CinemaPulse Started!")
    print("="*80)
    if use_dynamodb:
        print(f"💾 Mode: ✅ DynamoDB (Data persists)")
        print(f"📊 Tables:")
        print(f"   - CinemaPulse_Users")
        print(f"   - CinemaPulse_Reviews")
        print(f"   - CinemaPulse_Movies")
    else:
        print(f"💾 Mode: ⚠️  IN-MEMORY (Data will NOT persist)")
    print(f"📍 Home: http://127.0.0.1:5000")
    print(f"📍 Movies: http://127.0.0.1:5000/movies")
    print(f"📍 Analytics: http://127.0.0.1:5000/analytics")
    print("="*80 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
