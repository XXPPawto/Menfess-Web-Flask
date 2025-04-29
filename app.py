from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import secrets
from flask_paginate import Pagination, get_page_parameter
import re
import uuid

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///menfess.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configurations
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
app.config['PROFILE_PICS_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics')
app.config['VOICE_NOTES_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'voice_notes')
app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['ALLOWED_AUDIO_EXTENSIONS'] = {'mp3', 'wav', 'ogg', 'webm'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Create upload directories if they don't exist
os.makedirs(app.config['PROFILE_PICS_FOLDER'], exist_ok=True)
os.makedirs(app.config['VOICE_NOTES_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Define models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # user, moderator, admin
    is_suspended = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    menfesses = db.relationship('Menfess', backref='author', lazy=True)
    theme_preference = db.Column(db.String(10), default='light')  # light or dark
    profile_picture = db.Column(db.String(200), default='default.png')
    comments = db.relationship('Comment', backref='author', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    menfesses = db.relationship('Menfess', backref='category_rel', lazy=True)

class Menfess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    reports = db.relationship('Report', backref='menfess', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='menfess', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='menfess', lazy=True, cascade="all, delete-orphan")
    voice_note = db.Column(db.String(200), nullable=True)
    display_name = db.Column(db.String(100), nullable=True)
    
    # Function to process commands in menfess content
    def process_commands(self):
        # Process #bold# command
        content = re.sub(r'#bold#(.*?)#bold#', r'<strong>\1</strong>', self.content)
        # Process #italic# command
        content = re.sub(r'#italic#(.*?)#italic#', r'<em>\1</em>', content)
        # Process #color:color_name# command
        content = re.sub(r'#color:(.*?)#(.*?)#color#', r'<span style="color:\1">\2</span>', content)
        # Process #quote# command
        content = re.sub(r'#quote#(.*?)#quote#', r'<blockquote>\1</blockquote>', content)
        return content

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    menfess_id = db.Column(db.Integer, db.ForeignKey('menfess.id'), nullable=False)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    menfess_id = db.Column(db.Integer, db.ForeignKey('menfess.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    menfess_id = db.Column(db.Integer, db.ForeignKey('menfess.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add unique constraint to prevent multiple likes from the same user
    __table_args__ = (db.UniqueConstraint('menfess_id', 'user_id', name='unique_like'),)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper functions
def allowed_image_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_IMAGE_EXTENSIONS']

def allowed_audio_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_AUDIO_EXTENSIONS']

def save_profile_picture(file):
    if file and allowed_image_file(file.filename):
        filename = secure_filename(file.filename)
        # Generate unique filename to prevent overwriting
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['PROFILE_PICS_FOLDER'], unique_filename)
        file.save(file_path)
        return unique_filename
    return None

def save_voice_note(file):
    if file and allowed_audio_file(file.filename):
        filename = secure_filename(file.filename)
        # Generate unique filename to prevent overwriting
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['VOICE_NOTES_FOLDER'], unique_filename)
        file.save(file_path)
        return unique_filename
    return None

# Create all tables
with app.app_context():
    db.create_all()
    # Create admin user if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
    
    # Create default categories if they don't exist
    default_categories = [
        {'name': 'General', 'description': 'General discussions and topics'},
        {'name': 'Confession', 'description': 'Personal confessions and secrets'},
        {'name': 'Question', 'description': 'Questions and inquiries'},
        {'name': 'Story', 'description': 'Personal stories and experiences'},
        {'name': 'Advice', 'description': 'Seeking or giving advice'}
    ]
    
    for cat in default_categories:
        existing_category = Category.query.filter_by(name=cat['name']).first()
        if not existing_category:
            new_category = Category(name=cat['name'], description=cat['description'])
            db.session.add(new_category)
    
    db.session.commit()

# Routes for file uploads
@app.route('/uploads/profile_pics/<filename>')
def profile_pic(filename):
    return send_from_directory(app.config['PROFILE_PICS_FOLDER'], filename)

@app.route('/uploads/voice_notes/<filename>')
def voice_note(filename):
    return send_from_directory(app.config['VOICE_NOTES_FOLDER'], filename)

# Routes
@app.route('/')
def index():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 5  # Number of menfesses per page
    
    # Get category filter
    category_id = request.args.get('category', type=int)
    
    # Base query
    menfesses_query = Menfess.query.filter_by(is_approved=True)
    
    # Apply category filter if provided
    if category_id:
        menfesses_query = menfesses_query.filter_by(category_id=category_id)
    
    # Order by creation date
    menfesses_query = menfesses_query.order_by(Menfess.created_at.desc())
    
    # Get total count
    total = menfesses_query.count()
    
    # Create pagination
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    
    # Get paginated results
    menfesses = menfesses_query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Get like counts and comment counts for each menfess
    for menfess in menfesses:
        menfess.like_count = Like.query.filter_by(menfess_id=menfess.id).count()
        menfess.comment_count = Comment.query.filter_by(menfess_id=menfess.id).count()
        if current_user.is_authenticated:
            menfess.user_liked = Like.query.filter_by(menfess_id=menfess.id, user_id=current_user.id).first() is not None
        else:
            menfess.user_liked = False
    
    # Get all categories for the filter
    categories = Category.query.all()
    
    # Get current category name if filter is applied
    current_category = None
    if category_id:
        current_category = Category.query.get(category_id)
    
    return render_template('index.html', 
                          menfesses=menfesses, 
                          pagination=pagination, 
                          categories=categories,
                          current_category=current_category)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username or email already exists
        user_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()
        
        if user_exists:
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        if email_exists:
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        
        # Handle profile picture upload if provided
        profile_pic = request.files.get('profile_picture')
        if profile_pic and profile_pic.filename:
            pic_filename = save_profile_picture(profile_pic)
            if pic_filename:
                new_user.profile_picture = pic_filename
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))
        
        if user.is_suspended:
            flash('Your account has been suspended', 'danger')
            return redirect(url_for('login'))
        
        login_user(user)
        flash('Login successful!', 'success')
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        theme = request.form.get('theme_preference')
        
        # Check if username already exists
        user_exists = User.query.filter(User.username == username, User.id != current_user.id).first()
        if user_exists:
            flash('Username already exists', 'danger')
            return redirect(url_for('profile'))
        
        # Check if email already exists
        email_exists = User.query.filter(User.email == email, User.id != current_user.id).first()
        if email_exists:
            flash('Email already exists', 'danger')
            return redirect(url_for('profile'))
        
        current_user.username = username
        current_user.email = email
        current_user.theme_preference = theme
        
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            current_user.password = generate_password_hash(new_password)
        
        # Handle profile picture upload if provided
        profile_pic = request.files.get('profile_picture')
        if profile_pic and profile_pic.filename:
            pic_filename = save_profile_picture(profile_pic)
            if pic_filename:
                # Delete old profile picture if it's not the default
                if current_user.profile_picture != 'default.png':
                    try:
                        old_pic_path = os.path.join(app.config['PROFILE_PICS_FOLDER'], current_user.profile_picture)
                        if os.path.exists(old_pic_path):
                            os.remove(old_pic_path)
                    except Exception as e:
                        print(f"Error deleting old profile picture: {e}")
                
                current_user.profile_picture = pic_filename
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html')

@app.route('/toggle-theme', methods=['POST'])
def toggle_theme():
    theme = request.json.get('theme')
    
    if current_user.is_authenticated:
        current_user.theme_preference = theme
        db.session.commit()
        return jsonify({'status': 'success', 'theme': theme})
    else:
        return jsonify({'status': 'success', 'theme': theme})

@app.route('/post-menfess', methods=['GET', 'POST'])
@login_required
def post_menfess():
    if current_user.is_suspended:
        flash('Your account has been suspended', 'danger')
        return redirect(url_for('index'))
    
    categories = Category.query.all()
    
    if request.method == 'POST':
        content = request.form.get('content')
        category_id = request.form.get('category_id')
        display_name_type = request.form.get('display_name_type')
        custom_name = request.form.get('custom_name')
        
        if not content:
            flash('Content cannot be empty', 'danger')
            return redirect(url_for('post_menfess'))
        
        # Determine display name based on user selection
        display_name = None
        if display_name_type == 'username':
            display_name = current_user.username
        elif display_name_type == 'custom' and custom_name:
            display_name = custom_name
        # If anonymous or invalid selection, leave display_name as None
        
        new_menfess = Menfess(
            content=content,
            user_id=current_user.id,
            category_id=category_id,
            is_approved=current_user.role in ['admin', 'moderator'],  # Auto-approve for admins and moderators
            display_name=display_name
        )
        
        # Handle voice note upload if provided
        voice_note = request.files.get('voice_note')
        if voice_note and voice_note.filename:
            voice_filename = save_voice_note(voice_note)
            if voice_filename:
                new_menfess.voice_note = voice_filename
        
        db.session.add(new_menfess)
        db.session.commit()
        
        if current_user.role in ['admin', 'moderator']:
            flash('Menfess posted successfully', 'success')
        else:
            flash('Menfess submitted for approval', 'success')
        
        return redirect(url_for('index'))
    
    return render_template('post_menfess.html', categories=categories)

@app.route('/my-menfesses')
@login_required
def my_menfesses():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 5  # Number of menfesses per page
    
    # Get category filter
    category_id = request.args.get('category', type=int)
    
    # Base query
    menfesses_query = Menfess.query.filter_by(user_id=current_user.id)
    
    # Apply category filter if provided
    if category_id:
        menfesses_query = menfesses_query.filter_by(category_id=category_id)
    
    # Order by creation date
    menfesses_query = menfesses_query.order_by(Menfess.created_at.desc())
    
    # Get total count
    total = menfesses_query.count()
    
    # Create pagination
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    
    # Get paginated results
    menfesses = menfesses_query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Get comment counts for each menfess
    for menfess in menfesses:
        menfess.comment_count = Comment.query.filter_by(menfess_id=menfess.id).count()
    
    # Get all categories for the filter
    categories = Category.query.all()
    
    # Get current category name if filter is applied
    current_category = None
    if category_id:
        current_category = Category.query.get(category_id)
    
    return render_template('my_menfesses.html', 
                          menfesses=menfesses, 
                          pagination=pagination,
                          categories=categories,
                          current_category=current_category)

@app.route('/delete-menfess/<int:id>')
@login_required
def delete_menfess(id):
    menfess = Menfess.query.get_or_404(id)
    
    if menfess.user_id != current_user.id and current_user.role not in ['admin', 'moderator']:
        abort(403)
    
    # Delete voice note file if exists
    if menfess.voice_note:
        try:
            voice_note_path = os.path.join(app.config['VOICE_NOTES_FOLDER'], menfess.voice_note)
            if os.path.exists(voice_note_path):
                os.remove(voice_note_path)
        except Exception as e:
            print(f"Error deleting voice note: {e}")
    
    db.session.delete(menfess)
    db.session.commit()
    
    flash('Menfess deleted successfully', 'success')
    return redirect(url_for('my_menfesses'))

@app.route('/report-menfess/<int:id>', methods=['GET', 'POST'])
@login_required
def report_menfess(id):
    menfess = Menfess.query.get_or_404(id)
    
    if request.method == 'POST':
        reason = request.form.get('reason')
        
        if not reason:
            flash('Reason cannot be empty', 'danger')
            return redirect(url_for('report_menfess', id=id))
        
        new_report = Report(
            reason=reason,
            menfess_id=id,
            reporter_id=current_user.id
        )
        
        db.session.add(new_report)
        db.session.commit()
        
        flash('Menfess reported successfully', 'success')
        return redirect(url_for('index'))
    
    return render_template('report_menfess.html', menfess=menfess)

# Add a route for liking/unliking menfesses
@app.route('/like-menfess/<int:id>', methods=['POST'])
@login_required
def like_menfess(id):
    menfess = Menfess.query.get_or_404(id)
    
    # Check if user already liked this menfess
    existing_like = Like.query.filter_by(menfess_id=id, user_id=current_user.id).first()
    
    if existing_like:
        # Unlike
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({'status': 'unliked', 'likes': Like.query.filter_by(menfess_id=id).count()})
    else:
        # Like
        new_like = Like(menfess_id=id, user_id=current_user.id)
        db.session.add(new_like)
        db.session.commit()
        return jsonify({'status': 'liked', 'likes': Like.query.filter_by(menfess_id=id).count()})

# Comment routes
@app.route('/menfess/<int:id>/comments')
def view_comments(id):
    menfess = Menfess.query.get_or_404(id)
    
    # Check if menfess is approved or if current user is the author or admin/moderator
    if not menfess.is_approved and (not current_user.is_authenticated or 
                                   (current_user.id != menfess.user_id and 
                                    current_user.role not in ['admin', 'moderator'])):
        abort(404)
    
    # Get comments for this menfess
    comments = Comment.query.filter_by(menfess_id=id).order_by(Comment.created_at.asc()).all()
    
    # Get like count
    menfess.like_count = Like.query.filter_by(menfess_id=menfess.id).count()
    if current_user.is_authenticated:
        menfess.user_liked = Like.query.filter_by(menfess_id=menfess.id, user_id=current_user.id).first() is not None
    else:
        menfess.user_liked = False
    
    return render_template('view_comments.html', menfess=menfess, comments=comments)

@app.route('/menfess/<int:id>/add-comment', methods=['POST'])
@login_required
def add_comment(id):
    menfess = Menfess.query.get_or_404(id)
    
    # Check if menfess is approved or if current user is the author or admin/moderator
    if not menfess.is_approved and (current_user.id != menfess.user_id and 
                                   current_user.role not in ['admin', 'moderator']):
        abort(404)
    
    content = request.form.get('content')
    
    if not content:
        flash('Comment cannot be empty', 'danger')
        return redirect(url_for('view_comments', id=id))
    
    new_comment = Comment(
        content=content,
        user_id=current_user.id,
        menfess_id=id
    )
    
    db.session.add(new_comment)
    db.session.commit()
    
    flash('Comment added successfully', 'success')
    return redirect(url_for('view_comments', id=id))

@app.route('/delete-comment/<int:id>')
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    menfess_id = comment.menfess_id
    
    # Check if current user is the comment author or admin/moderator
    if comment.user_id != current_user.id and current_user.role not in ['admin', 'moderator']:
        abort(403)
    
    db.session.delete(comment)
    db.session.commit()
    
    flash('Comment deleted successfully', 'success')
    return redirect(url_for('view_comments', id=menfess_id))

# Admin routes
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        abort(403)
    
    pending_menfesses = Menfess.query.filter_by(is_approved=False).count()
    reports = Report.query.count()
    users = User.query.count()
    
    return render_template('admin/index.html', 
                          pending_menfesses=pending_menfesses, 
                          reports=reports, 
                          users=users)

@app.route('/admin/menfesses')
@login_required
def admin_menfesses():
    if current_user.role not in ['admin', 'moderator']:
        abort(403)
    
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10  # Number of menfesses per page
    
    # Get category filter
    category_id = request.args.get('category', type=int)
    
    # Base query
    menfesses_query = Menfess.query.filter_by(is_approved=False)
    
    # Apply category filter if provided
    if category_id:
        menfesses_query = menfesses_query.filter_by(category_id=category_id)
    
    # Order by creation date
    menfesses_query = menfesses_query.order_by(Menfess.created_at.desc())
    
    # Get total count
    total = menfesses_query.count()
    
    # Create pagination
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    
    # Get paginated results
    menfesses = menfesses_query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Get all categories for the filter
    categories = Category.query.all()
    
    # Get current category name if filter is applied
    current_category = None
    if category_id:
        current_category = Category.query.get(category_id)
    
    return render_template('admin/menfesses.html', 
                          menfesses=menfesses, 
                          pagination=pagination,
                          categories=categories,
                          current_category=current_category)

@app.route('/admin/approve-menfess/<int:id>')
@login_required
def approve_menfess(id):
    if current_user.role not in ['admin', 'moderator']:
        abort(403)
    
    menfess = Menfess.query.get_or_404(id)
    menfess.is_approved = True
    db.session.commit()
    
    flash('Menfess approved successfully', 'success')
    return redirect(url_for('admin_menfesses'))

@app.route('/admin/reject-menfess/<int:id>')
@login_required
def reject_menfess(id):
    if current_user.role not in ['admin', 'moderator']:
        abort(403)
    
    menfess = Menfess.query.get_or_404(id)
    
    # Delete voice note file if exists
    if menfess.voice_note:
        try:
            voice_note_path = os.path.join(app.config['VOICE_NOTES_FOLDER'], menfess.voice_note)
            if os.path.exists(voice_note_path):
                os.remove(voice_note_path)
        except Exception as e:
            print(f"Error deleting voice note: {e}")
    
    db.session.delete(menfess)
    db.session.commit()
    
    flash('Menfess rejected successfully', 'success')
    return redirect(url_for('admin_menfesses'))

@app.route('/admin/reports')
@login_required
def admin_reports():
    if current_user.role not in ['admin', 'moderator']:
        abort(403)
    
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10  # Number of reports per page
    
    reports_query = Report.query.order_by(Report.created_at.desc())
    total = reports_query.count()
    
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    reports = reports_query.offset((page - 1) * per_page).limit(per_page).all()
    
    return render_template('admin/reports.html', reports=reports, pagination=pagination)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        abort(403)
    
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10  # Number of users per page
    
    users_query = User.query
    total = users_query.count()
    
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    users = users_query.offset((page - 1) * per_page).limit(per_page).all()
    
    return render_template('admin/users.html', users=users, pagination=pagination)

@app.route('/admin/edit-user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        
        # Check if username already exists
        user_exists = User.query.filter(User.username == username, User.id != user.id).first()
        if user_exists:
            flash('Username already exists', 'danger')
            return redirect(url_for('edit_user', id=id))
        
        # Check if email already exists
        email_exists = User.query.filter(User.email == email, User.id != user.id).first()
        if email_exists:
            flash('Email already exists', 'danger')
            return redirect(url_for('edit_user', id=id))
        
        user.username = username
        user.email = email
        user.role = role
        
        # Handle profile picture upload if provided
        profile_pic = request.files.get('profile_picture')
        if profile_pic and profile_pic.filename:
            pic_filename = save_profile_picture(profile_pic)
            if pic_filename:
                # Delete old profile picture if it's not the default
                if user.profile_picture != 'default.png':
                    try:
                        old_pic_path = os.path.join(app.config['PROFILE_PICS_FOLDER'], user.profile_picture)
                        if os.path.exists(old_pic_path):
                            os.remove(old_pic_path)
                    except Exception as e:
                        print(f"Error deleting old profile picture: {e}")
                
                user.profile_picture = pic_filename
        
        db.session.commit()
        flash('User updated successfully', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/toggle-suspend/<int:id>')
@login_required
def toggle_suspend(id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(id)
    
    if user.role == 'admin':
        flash('Cannot suspend admin users', 'danger')
        return redirect(url_for('admin_users'))
    
    user.is_suspended = not user.is_suspended
    db.session.commit()
    
    if user.is_suspended:
        flash(f'User {user.username} has been suspended', 'success')
    else:
        flash(f'User {user.username} has been unsuspended', 'success')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    if current_user.role != 'admin':
        abort(403)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Check if category already exists
        category_exists = Category.query.filter_by(name=name).first()
        if category_exists:
            flash('Category already exists', 'danger')
            return redirect(url_for('admin_categories'))
        
        new_category = Category(name=name, description=description)
        db.session.add(new_category)
        db.session.commit()
        
        flash('Category added successfully', 'success')
        return redirect(url_for('admin_categories'))
    
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/edit-category/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    if current_user.role != 'admin':
        abort(403)
    
    category = Category.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Check if category name already exists
        category_exists = Category.query.filter(Category.name == name, Category.id != category.id).first()
        if category_exists:
            flash('Category name already exists', 'danger')
            return redirect(url_for('edit_category', id=id))
        
        category.name = name
        category.description = description
        
        db.session.commit()
        flash('Category updated successfully', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/edit_category.html', category=category)

@app.route('/admin/delete-category/<int:id>')
@login_required
def delete_category(id):
    if current_user.role != 'admin':
        abort(403)
    
    category = Category.query.get_or_404(id)
    
    # Check if there are menfesses in this category
    menfesses_count = Menfess.query.filter_by(category_id=id).count()
    if menfesses_count > 0:
        flash(f'Cannot delete category. It contains {menfesses_count} menfesses.', 'danger')
        return redirect(url_for('admin_categories'))
    
    db.session.delete(category)
    db.session.commit()
    
    flash('Category deleted successfully', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/delete-reported-menfess/<int:id>')
@login_required
def delete_reported_menfess(id):
    if current_user.role not in ['admin', 'moderator']:
        abort(403)
    
    menfess = Menfess.query.get_or_404(id)
    
    # Delete voice note file if exists
    if menfess.voice_note:
        try:
            voice_note_path = os.path.join(app.config['VOICE_NOTES_FOLDER'], menfess.voice_note)
            if os.path.exists(voice_note_path):
                os.remove(voice_note_path)
        except Exception as e:
            print(f"Error deleting voice note: {e}")
    
    # Delete the menfess (reports will be cascade deleted)
    db.session.delete(menfess)
    db.session.commit()
    
    flash('Reported menfess deleted successfully', 'success')
    return redirect(url_for('admin_reports'))

if __name__ == '__main__':
    app.run(debug=True)
