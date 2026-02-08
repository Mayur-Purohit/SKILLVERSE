import eventlet
eventlet.monkey_patch()

from sqlalchemy.pool import NullPool
from flask import Flask, render_template, request, session, redirect, url_for, Response, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from authlib.integrations.flask_client import OAuth
import base64
import io
import json
import os
import requests
from email_service import init_mail, send_welcome_email, send_task_reminder_email
from pytz import timezone, utc

import os
import sys
import time
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Allow OAuth over HTTP for local testing
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Check for required API Key
if not os.getenv("AI_API_KEY"):
    pass 

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


from werkzeug.middleware.proxy_fix import ProxyFix
from whitenoise import WhiteNoise

app = Flask(__name__)
# Fix for Render/Heroku (Reverse Proxy) - Critical for OAuth and HTTPS
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# Serve static files directly efficiently
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
# Production: Must use DATABASE_URL from environment (e.g. Render)
database_url = os.getenv('DATABASE_URL', 'sqlite:///StudyVerse.db')

# FIX: Check for common misconfiguration on Render (using localhost URL in production)
is_render = os.environ.get('RENDER') or os.environ.get('render')
if is_render and ('localhost' in database_url or '127.0.0.1' in database_url):
    print("WARNING: Localhost database URL detected in Render environment. This will fail.")
    print("Falling back to ephemeral SQLite to prevent crash. Please fix DATABASE_URL in Render Dashboard.")
    database_url = 'sqlite:///StudyVerse_fallback.db'

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



# Connection pool settings for cloud PostgreSQL (Render, Heroku, etc.)
# Optimized for concurrent users - prevents crashes and SSL errors
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'poolclass': NullPool,      # Disable pooling to fix "un-acquired lock" with eventlet
    'pool_pre_ping': True,     # Validate connections
}
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

# Google OAuth Config - Use environment variables
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Session Configuration - Environment-aware security
IS_PRODUCTION = os.getenv('RENDER', False) or os.getenv('PRODUCTION', False)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION  # True on HTTPS (Render)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_SECURE'] = IS_PRODUCTION  # True on HTTPS
app.config['REMEMBER_COOKIE_HTTPONLY'] = True

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize SocketIO with production settings - optimized for concurrent users
socketio = SocketIO(
    app,
    cors_allowed_origins="*",  # Allow all origins (or set to your domain)
    async_mode='threading',      # Use threading for compatibility with Python 3.13
    ping_timeout=120,           # 2 min timeout for slow connections
    ping_interval=25,           # Keep connection alive every 25s
    max_http_buffer_size=1e8,   # 100MB max message size
    logger=False,               # Disable noisy logs
    engineio_logger=False,      # Disable noisy engineio logs
    # Support both polling and websocket, starting with polling for stability
    transports=['polling', 'websocket'],
    cookie=None                 # Helps avoid session conflicts on some proxies
)

# AI API Configuration
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_TYPE = os.getenv("AI_API_TYPE", "google")

if GEMINI_AVAILABLE and AI_API_KEY:
    try:
        genai.configure(api_key=AI_API_KEY)
    except Exception as e:
        print(f"Failed to configure Gemini: {e}")

# IST Timezone
IST = timezone('Asia/Kolkata')

# Timezone Helper: Convert UTC datetime to IST formatted time
def to_ist_time(utc_datetime):
    """Convert UTC datetime to IST and return formatted 12-hour time string."""
    if not utc_datetime:
        return ""
    
    # Ensure datetime is timezone-aware (UTC)
    if utc_datetime.tzinfo is None:
        utc_datetime = utc.localize(utc_datetime)
    
    # Convert to IST
    ist_datetime = utc_datetime.astimezone(IST)
    
    # Format as 12-hour time with AM/PM
    return ist_datetime.strftime('%I:%M %p')

AI_MODEL = os.getenv("AI_MODEL", "models/gemini-2.5-flash")


db = SQLAlchemy(app)

# Initialize email service
mail = init_mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth'

# Jinja Template Filter for IST Time (must be after app is configured)
@app.template_filter('ist_time')
def ist_time_filter(utc_datetime):
    """Jinja filter to convert UTC datetime to IST time string."""
    return to_ist_time(utc_datetime)

# Also add to_ist_time as a global function for templates
app.jinja_env.globals.update(to_ist_time=to_ist_time)



# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True) # Nullable for OAuth users
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    google_id = db.Column(db.String(100), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    cover_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Gamification Fields
    total_xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_activity_date = db.Column(db.Date, nullable=True)
    about_me = db.Column(db.Text, nullable=True)

    @property
    def rank_info(self):
        """Returns the dictionary of rank details (name, icon, color)."""
        return GamificationService.get_rank(self.level)

    @property
    def active_frame_color(self):
        """Returns the color of the user's currently active frame, or None."""
        try:
            active_items = UserItem.query.filter_by(user_id=self.id, is_active=True).all()
            for u_item in active_items:
                cat_item = ShopService.ITEMS.get(u_item.item_id)
                if cat_item and cat_item.get('type') == 'frame':
                    return cat_item.get('color')
        except Exception:
            pass
        return None

    @property
    def has_active_theme(self):
        """Returns True if the user has an active theme equipped, False otherwise."""
        try:
            active_items = UserItem.query.filter_by(user_id=self.id, is_active=True).all()
            for u_item in active_items:
                cat_item = ShopService.ITEMS.get(u_item.item_id)
                if cat_item and cat_item.get('type') == 'theme':
                    return True
        except Exception:
            pass
        return False

    @property
    def rank(self):
        """Backward compatibility for templates using user.rank."""
        return self.rank_info['name']

    @property
    def rank_name(self):
        """Backward compatibility for templates using user.rank_name."""
        return self.rank_info['name']

    @property
    def rank_icon(self):
        """Backward compatibility for templates using user.rank_icon."""
        return self.rank_info['icon']

    @property
    def rank_color(self):
        """Backward compatibility for templates using user.rank_color."""
        return self.rank_info['color']
    
    def get_avatar(self, size=200):
        if self.profile_image and "ui-avatars.com" not in self.profile_image:
            return self.profile_image
        
        # Robust initial extraction
        f_name = (self.first_name or '').strip()
        l_name = (self.last_name or '').strip()
        
        f = f_name[0] if f_name else ''
        l = l_name[0] if l_name else ''
        
        # Force at least one character
        initials = f"{f}{l}".upper()
        if not initials:
            initials = "U"
            
        return f"https://ui-avatars.com/api/?name={initials}&background=0ea5e9&color=fff&size={size}"
    
    def to_dict(self):
        rank_data = GamificationService.get_rank(self.level)
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'level': self.level,
            'total_xp': self.total_xp,
            'rank': rank_data['name'],
            'rank_icon': rank_data['icon'],
            'rank_color': rank_data['color'],
            'avatar': self.get_avatar(),
            'is_public': self.is_public_profile
        }

    # Privacy & Status
    is_public_profile = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # We can use backrefs in User if preferred, or just query directly
    # user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('friendships_sent', lazy='dynamic'))
    # friend = db.relationship('User', foreign_keys=[friend_id], backref=db.backref('friendships_received', lazy='dynamic'))

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), default='fa-medal') # FontAwesome class
    criteria_type = db.Column(db.String(50)) # e.g., 'streak', 'xp', 'wins'
    criteria_value = db.Column(db.Integer)

class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='badges')
    badge = db.relationship('Badge')

class XPHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source = db.Column(db.String(50), nullable=False) # battle, task, focus
    amount = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class GamificationService:
    """Central logic for XP, Levels, Ranks, and Badges."""
    
    RANKS = {
        (1, 5): ('Bronze', 'fa-shield-halved', '#CD7F32'),
        (6, 10): ('Silver', 'fa-shield-halved', '#C0C0C0'),
        (11, 20): ('Gold', 'fa-shield-halved', '#FFD700'),
        (21, 35): ('Platinum', 'fa-gem', '#E5E4E2'),
        (36, 50): ('Diamond', 'fa-gem', '#b9f2ff'),
        (51, 75): ('Heroic', 'fa-crown', '#ff4d4d'),
        (76, 100): ('Master', 'fa-crown', '#ff0000'),
        (101, 10000000000000): ('Grandmaster', 'fa-dragon', '#800080')
    }

    @staticmethod
    def calculate_level(total_xp):
        # Level = floor(total_xp / 500) + 1
        return max(1, int(total_xp / 500) + 1)

    @staticmethod
    def get_rank(level):
        if level is None: level = 1
        for (min_lvl, max_lvl), (name, icon, color) in GamificationService.RANKS.items():
            if min_lvl <= level <= max_lvl:
                return {'name': name, 'icon': icon, 'color': color}
        return {'name': 'Bronze', 'icon': 'fa-shield-halved', 'color': '#CD7F32'}

    @staticmethod
    def add_xp(user_id, source, amount, force_deduct=False):
        user = User.query.get(user_id)
        if not user:
            return

        # 1. Fetch ALL active power-ups for the user
        active_powerups = ActivePowerUp.query.filter_by(
            user_id=user.id,
            is_active=True
        ).all()
        
        # 2. Categorize and clean up expired power-ups
        xp_multiplier = 1.0
        time_multiplier = 1.0
        has_protection = False
        active_boost = None

        for powerup in active_powerups:
            if powerup.is_expired():
                powerup.is_active = False
                continue
            
            # Fetch item details from catalog to know the effect type
            item_id = powerup.power_up_id
            cat_item = ShopService.ITEMS.get(item_id)
            if not cat_item: continue

            effect = cat_item.get('effect')
            
            if effect in ['xp_multiplier', 'mega_xp_multiplier']:
                if powerup.multiplier > xp_multiplier:
                    xp_multiplier = powerup.multiplier
                    active_boost = item_id
            elif effect == 'time_multiplier':
                if powerup.multiplier > time_multiplier:
                    time_multiplier = powerup.multiplier
            elif effect == 'xp_protection':
                has_protection = True
        
        # 3. Handle XP loss protection
        if amount < 0:
            if not force_deduct and has_protection:
                return {'earned': 0, 'message': 'XP Protection Active! No XP lost.'}
            
            # Direct deduction logic
            user.total_xp = max(0, user.total_xp + amount) # Check bounds? Or allow negative? keeping 0 floor
            
            # Log negative history
            log = XPHistory(user_id=user.id, source=source, amount=amount)
            db.session.add(log)
            db.session.commit()
            return {'earned': amount, 'new_total': user.total_xp}

        # 4. Apply special multipliers based on source (e.g., Double Time for focus)
        actual_multiplier = xp_multiplier
        if source == 'focus' and time_multiplier > 1.0:
            # If both XP boost and Double Time are active, they might stack or we take the highest.
            # Usually, Double Time specifically doubles the focus reward.
            actual_multiplier *= time_multiplier

        # 5. Cap Focus XP daily (Check BEFORE multipliers to keep cap consistent)
        if source == 'focus':
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            daily_focus_xp = db.session.query(db.func.sum(XPHistory.amount))\
                .filter(XPHistory.user_id == user.id, XPHistory.source == 'focus', XPHistory.timestamp >= today_start)\
                .scalar() or 0
            
            # Simple daily cap logic: max 500 XP from focus per day
            if daily_focus_xp >= 500:
                return {'earned': 0, 'message': 'Daily Focus XP cap reached!'}
            
            if daily_focus_xp + amount > 500:
                amount = 500 - daily_focus_xp

        if amount <= 0:
            return

        # Apply multiplier
        original_amount = amount
        if actual_multiplier > 1.0:
            amount = int(amount * actual_multiplier)

        user.total_xp += amount
        
        # Level Up Check
        new_level = GamificationService.calculate_level(user.total_xp)
        leveled_up = False
        if new_level > user.level:
            user.level = new_level
            leveled_up = True
            
        # Log History
        log = XPHistory(user_id=user.id, source=source, amount=amount)
        db.session.add(log)
        
        # Update Streak (if not already updated today)
        GamificationService.update_streak(user)
        
        # Check Badges
        GamificationService.check_badges(user)
        
        db.session.commit()
        
        result = {
            'earned': amount, 
            'new_total': user.total_xp, 
            'leveled_up': leveled_up,
            'new_level': user.level,
            'rank': GamificationService.get_rank(user.level)
        }
        
        # Add multiplier info if active
        if actual_multiplier > 1.0:
            result['multiplier'] = actual_multiplier
            result['base_amount'] = original_amount
            result['boost_active'] = active_boost
        
        return result

    @staticmethod
    def update_streak(user):
        today = datetime.utcnow().date()
        if user.last_activity_date == today:
            return # Already active today
        
        if user.last_activity_date == today - timedelta(days=1):
            user.current_streak += 1
        else:
            user.current_streak = 1 # Reset if missed a day (or first time)
            
        user.last_activity_date = today
        if user.current_streak > user.longest_streak:
            user.longest_streak = user.current_streak

    @staticmethod
    def check_badges(user):
        # 1. Streak Badges
        if user.current_streak >= 30:
            GamificationService.award_badge(user, 'Consistency King')
        
        # 2. XP Badges (Level based roughly)
        if user.level >= 10:
             GamificationService.award_badge(user, 'Rising Star')
        if user.level >= 50:
             GamificationService.award_badge(user, 'Dedicated Scholar')
        if user.level >= 100:
             GamificationService.award_badge(user, 'Centurion')
             
        # More rules can be added here
        
    @staticmethod
    def award_badge(user, badge_name):
        badge = Badge.query.filter_by(name=badge_name).first()
        if not badge:
            # Create default if missing (lazy init)
            if badge_name == 'Consistency King':
                badge = Badge(name='Consistency King', description='Achieve a 30-day streak', icon='fa-fire', criteria_type='streak', criteria_value=30)
            elif badge_name == 'Rising Star':
                badge = Badge(name='Rising Star', description='Reach Level 10', icon='fa-star', criteria_type='level', criteria_value=10)
            elif badge_name == 'Dedicated Scholar':
                badge = Badge(name='Dedicated Scholar', description='Reach Level 50', icon='fa-book-open', criteria_type='level', criteria_value=50)
            elif badge_name == 'Centurion':
                badge = Badge(name='Centurion', description='Reach Level 100', icon='fa-crown', criteria_type='level', criteria_value=100)
            else:
                return 
            db.session.add(badge)
            db.session.commit()
            
        if not UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first():
            ub = UserBadge(user_id=user.id, badge_id=badge.id)
            db.session.add(ub)



class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='medium')
    due_date = db.Column(db.String(50))
    # Time specific fields
    due_time = db.Column(db.String(20), nullable=True) # HH:MM format
    is_notified = db.Column(db.Boolean, default=False)
    
    category = db.Column(db.String(50))
    is_group = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    syllabus_id = db.Column(db.Integer, db.ForeignKey('syllabus_document.id'), nullable=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Could add color, icon, etc. later

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    # We only care about the DATE for the log
    completed_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    is_group = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    mode = db.Column(db.String(20), default='focus')  # focus, shortBreak, longBreak
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class TopicProficiency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic_name = db.Column(db.String(200), nullable=False)
    proficiency = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invite_code = db.Column(db.String(10), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='uq_group_member'),
    )

class GroupChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='group_messages')

class SyllabusDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(100), nullable=False)
    extracted_text = db.Column(db.Text, nullable=True) # AI Context
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.String(50), nullable=False) # Format: YYYY-MM-DD
    time = db.Column(db.String(50), nullable=True)
    is_notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------------------
# Data Structures (DS) Utilities
# ------------------------------

class Stack:
    """Simple LIFO stack.

    Used for: Undo delete in Todos.
    """

    def __init__(self):
        self._items = []

    def push(self, item):
        self._items.append(item)

    def pop(self):
        if not self._items:
            return None
        return self._items.pop()

    def is_empty(self):
        return len(self._items) == 0


class LRUCache:
    """LRU Cache using dict + list (simplified).

    DS concept:
    - Hash map (dict) for O(1) key lookup
    - List to track usage order for eviction
    """

    def __init__(self, capacity=50):
        self.capacity = capacity
        self.cache = {}
        self.order = []  # most recent at end

    def get(self, key):
        if key not in self.cache:
            return None
        if key in self.order:
            self.order.remove(key)
        self.order.append(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache[key] = value
            if key in self.order:
                self.order.remove(key)
            self.order.append(key)
            return

        if len(self.cache) >= self.capacity:
            oldest = self.order.pop(0)
            del self.cache[oldest]

        self.cache[key] = value
        self.order.append(key)


# ------------------------------
# OOP Services
# ------------------------------

class AuthService:
    """Authentication service (OOP abstraction around auth logic)."""

    @staticmethod
    def create_user(email: str, password: str, first_name: str, last_name: str) -> "User":
        if User.query.filter_by(email=email).first():
            raise ValueError("Email already registered")

        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name,
        )
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def authenticate(email: str, password: str):
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists
        if not user:
            return None
        
        # Check if user has a password (not a Google OAuth user)
        if not user.password_hash:
            # User signed up with Google OAuth, no password set
            return None
        
        # Verify password
        if check_password_hash(user.password_hash, password):
            return user
        
        return None


class GroupService:
    """Group operations: create, join, membership check."""

    @staticmethod
    def _generate_invite_code(length: int = 6) -> str:
        import random
        import string

        alphabet = string.ascii_uppercase + string.digits
        return ''.join(random.choice(alphabet) for _ in range(length))

    @staticmethod
    def create_group(admin_user_id: int, name: str) -> Group:
        invite_code = GroupService._generate_invite_code()
        while Group.query.filter_by(invite_code=invite_code).first() is not None:
            invite_code = GroupService._generate_invite_code()

        group = Group(name=name, admin_id=admin_user_id, invite_code=invite_code)
        db.session.add(group)
        db.session.commit()

        db.session.add(GroupMember(group_id=group.id, user_id=admin_user_id))
        db.session.commit()
        return group

    @staticmethod
    def join_group(user_id: int, invite_code: str) -> Group:
        group = Group.query.filter_by(invite_code=invite_code).first()
        if not group:
            raise ValueError("Invalid invite code")

        existing = GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first()
        if existing:
            return group

        db.session.add(GroupMember(group_id=group.id, user_id=user_id))
        db.session.commit()
        return group

    @staticmethod
    def get_user_group(user_id: int):
        membership = GroupMember.query.filter_by(user_id=user_id).order_by(GroupMember.joined_at.desc()).first()
        if not membership:
            return None
        return Group.query.get(membership.group_id)


class SyllabusService:
    """PDF syllabus upload + extraction and retrieval (simple)."""

    @staticmethod
    def save_syllabus(user_id: int, filename: str, extracted_text: str) -> SyllabusDocument:
        # existing = SyllabusDocument.query.filter_by(user_id=user_id).first()
        # if existing:
        #     db.session.delete(existing)
        #     db.session.commit()

        doc = SyllabusDocument(user_id=user_id, filename=filename, extracted_text=extracted_text)
        db.session.add(doc)
        db.session.commit()
        return doc

    @staticmethod
    def get_syllabus_text(user_id: int) -> str:
        doc = SyllabusDocument.query.filter_by(user_id=user_id).first()
        return doc.extracted_text if doc else ""

    @staticmethod
    def extract_tasks_from_pdf(pdf_bytes: bytes) -> list:
        if not AI_API_KEY:
            raise ValueError("AI_API_KEY not configured")

        model_id = os.environ.get("GEMINI_PDF_MODEL", "models/gemini-2.5-flash")
        if "/" in model_id:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/{model_id}:generateContent?key={AI_API_KEY}"
        else:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={AI_API_KEY}"

        prompt = (
            "You are a study assistant. Analyze the attached PDF notes. "
            "Identify the main chapters and key topics. "
            "Output ONLY valid JSON in this exact format: "
            "{\"tasks\": [{\"title\": \"Chapter Name\", \"subtasks\": [\"Topic 1\", \"Topic 2\"]}]}"
        )

        pdf_data = base64.b64encode(pdf_bytes).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }

        response = requests.post(endpoint, json=payload, headers={'Content-Type': 'application/json'}, timeout=120)
        result_data = response.json() if response.text else {}

        if response.status_code != 200:
            error_msg = result_data.get("error", {}).get("message", response.text or "Unknown error")
            raise ValueError(f"Google Error: {error_msg}")

        if "error" in result_data:
            error_msg = result_data["error"].get("message", "Unknown API Error")
            raise ValueError(f"Google Error: {error_msg}")

        raw = ""
        if "candidates" in result_data and result_data["candidates"]:
            raw = result_data["candidates"][0]["content"]["parts"][0].get("text", "")
        if not raw:
            raise ValueError("AI could not read this PDF")

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()

        parsed = None
        # Try to parse JSON with multiple fallback approaches
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            try:
                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1 and end > start:
                    parsed = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        
        if parsed is None:
            raise ValueError("AI response could not be parsed as JSON. Please try again.")

        tasks = parsed.get("tasks", [])
        if not isinstance(tasks, list):
            raise ValueError("Invalid AI response: tasks is not a list")
        return tasks

    @staticmethod
    def build_chapters_from_todos(user_id: int, syllabus_id: int = None) -> list:
        query = Todo.query.filter_by(user_id=user_id, is_group=False)
        
        # If specific syllabus requested, filter by it
        if syllabus_id:
            query = query.filter_by(syllabus_id=syllabus_id)
        
        # If no syllabus ID, ideally we show tasks that are EITHER linked to active
        # OR linked to None (legacy), OR we just show everything?
        # User requested: "Active syllabus tasks no need to show completed course task"
        # Since we just migrated everything, we should enforce filtering if syllabus_id is passed.
        # If syllabus_id is None, maybe we just fetch ALL? 
        # But 'active' syllabus assumes the newest doc.
        
        todos = query.order_by(Todo.created_at.asc()).all()

        chapters = {}
        for t in todos:
            if not t.category:
                continue
            chapters.setdefault(t.category, []).append(t)

        result = []
        for category, items in chapters.items():
            total = len(items)
            completed = sum(1 for x in items if x.completed)
            percent = int((completed / total) * 100) if total else 0
            
            # Fetch proficiency for this chapter (category)
            prof_entry = TopicProficiency.query.filter_by(user_id=user_id, topic_name=category).first()
            proficiency = prof_entry.proficiency if prof_entry else 0
            
            result.append({
                'name': category,
                'todos': items,
                'total': total,
                'completed': completed,
                'percent': percent,
                'proficiency': proficiency
            })

        result.sort(key=lambda x: x['name'].lower())
        return result


# ------------------------------
# API HELPER (Fix for missing function)
# ------------------------------
def call_ai_api(messages):
    """
    Call Google Gemini API (or other configured AI).
    messages: list of dicts [{'role': 'user', 'content': '...'}]
    Returns: str (response content)
    """
    if not AI_API_KEY:
         raise ValueError("AI_API_KEY not configured. Please set it in .env")

    # Extract the last user prompt (Gemini is often stateless/one-shot via this simple helper, 
    # or we can build the history string if using the chat model properly).
    # For simplicity/robustness here:
    
    conversation_history = ""
    for m in messages:
        role = "User" if m['role'] == 'user' else "Model"
        conversation_history += f"{role}: {m['content']}\n"
    
    # We'll just use the last prompt if we want simple stateless, but history is good.
    # Actually, let's just send the last 2000 chars of history to avoid context limits if using free tier.
    final_prompt = conversation_history[-3000:] 

    try:
        model_id = os.environ.get("GEMINI_MODEL", "models/gemini-2.5-flash")
        
        # Use simple requests if genai lib issues, or if preferred.
        # But allow genai lib if available.
        if GEMINI_AVAILABLE:
            model = genai.GenerativeModel(model_id)
            # Create a chat session or just generate content
            # Mapping roles for Gemini (user/model)
            gemini_hist = []
            # We need to format specific for Gemini history if we use start_chat.
            # But generate_content is easier for one-off.
            
            response = model.generate_content(final_prompt)
            return response.text
            
        else:
            # Fallback to requests REST API
            if "/" in model_id:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/{model_id}:generateContent?key={AI_API_KEY}"
            else:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={AI_API_KEY}"

            payload = {
                "contents": [{
                    "parts": [{"text": final_prompt}]
                }]
            }
            
            r = requests.post(endpoint, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
            if r.status_code != 200:
                raise ValueError(f"API Error {r.status_code}: {r.text}")
                
            data = r.json()
            if 'candidates' in data and data['candidates']:
                return data['candidates'][0]['content']['parts'][0]['text']
            
            return "Error: No content returned."

    except Exception as e:
        print(f"AI API Call Failed: {e}")
        # Return a friendly error or re-raise
        # Re-raising allows the caller (ChatService) to catch and format nicely
        raise e


class ChatService:
    """Personal + group AI chat.

    Uses DS concept:
    - LRU cache to avoid repeated calls for same query.
    """

    _cache = LRUCache(capacity=100)

    @staticmethod
    def build_system_prompt(user: User, syllabus_text: str) -> str:
        base = (
            "You are StudyVerse, an expert AI Study Coach and academic mentor. "
            "Your goal is to help students learn effectively, stay motivated, and organize their studies.\n"
            "Guidelines:\n"
            "1. Be encouraging, structured, and clear. Use Markdown (bold, lists) for readability.\n"
            "2. The user has uploaded their syllabus/course material for REFERENCE. Do NOT generate solutions, summaries, or lessons from it unless the user EXPLICITLY asks.\n"
            "3. If the user says 'Hello' or similar, just greet them warmly and ask how you can help.\n"
            "4. Keep responses concise but helpful. Avoid long monologues unless necessary.\n"
            "5. Remember the context of the conversation."
        )
        if syllabus_text:
            base += "\n\n[REFERENCE MATERIAL - SYLLABUS/CONTENT]\n" + syllabus_text[:3000] + "\n[END REFERENCE MATERIAL]\n(Use the above material ONLY if the user asks about it.)"
        return base

    @staticmethod
    def generate_focus_plan(user: User) -> str:
        # Get pending tasks
        todos = Todo.query.filter_by(user_id=user.id, completed=False).limit(10).all()
        tasks_text = "\n".join([f"- {t.title} (Priority: {t.priority})" for t in todos])
        
        syllabus_text = SyllabusService.get_syllabus_text(user.id)
        
        prompt = (
            "You are a study coach. Based on the user's pending tasks and syllabus, "
            "create a short, actionable 3-step study plan for today. "
            "Format nicely with Markdown. Keep it encouraging.\n\n"
            f"Pending Tasks:\n{tasks_text}\n\n"
            f"Syllabus Context:\n{syllabus_text[:1000]}"
        )
        
        messages = [{'role': 'user', 'content': prompt}]
        return call_ai_api(messages)

    @staticmethod
    def generate_chat_response(user: User, message: str) -> str:
        # 1. Check Cache
        cached = ChatService._cache.get(message)
        if cached:
            return cached

        # 2. Get Context (Syllabus)
        syllabus_text = SyllabusService.get_syllabus_text(user.id)
        
        # 3. Build Prompt
        system_prompt = ChatService.build_system_prompt(user, syllabus_text)
        
        # We should ideally fetch recent chat history here for context window
        recent_chats = ChatMessage.query.filter_by(user_id=user.id, is_group=False).order_by(ChatMessage.created_at.desc()).limit(5).all()
        history = []
        for msg in reversed(recent_chats):
            history.append({'role': msg.role, 'content': msg.content})
            
        messages = history + [{'role': 'user', 'content': f"{system_prompt}\n\nUser Question: {message}"}]
        
        # 4. Call API
        try:
            response = call_ai_api(messages)
            # 5. Cache Result
            ChatService._cache.put(message, response)
            return response
        except Exception as e:
            return f"I'm having trouble connecting to my brain right now. Please try again later. (Error: {str(e)})"
            
    @staticmethod
    def personal_reply(user: User, message: str) -> str:
        """Wrapper for generate_chat_response for backward compatibility / keeping naming consistent in routes"""
        return ChatService.generate_chat_response(user, message)

@app.route('/api/ai/plan', methods=['GET'])
@login_required
def ai_plan():
    try:
        plan = ChatService.generate_focus_plan(current_user)
        return jsonify({'status': 'success', 'plan': plan})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    try:
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
    except:
        pass
    return redirect(url_for('auth'))

@app.route('/auth')
def auth():
    # Check if user is authenticated
    if current_user.is_authenticated:
        print(f"Auth Check: User {current_user.id} is authenticated. Redirecting to dashboard.")
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/signup', methods=['POST'])
def signup():
    """Create account using standard HTML form POST (no JSON)."""
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    if not email or not password:
        flash('Email and password are required.', 'error')
        return redirect(url_for('auth'))

    try:
        user = AuthService.create_user(email, password, first_name, last_name)
        
        # Send welcome email to new user
        try:
            send_welcome_email(user.email, user.first_name, user.last_name)
        except Exception as e:
            print(f"Failed to send welcome email: {e}")
            # Continue even if email fails
            
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('auth'))

    login_user(user, remember=True)  # Enable remember me for persistent sessions
    session.permanent = True
    return redirect(url_for('dashboard'))

@app.route('/signin', methods=['POST'])
def signin():
    """Sign in using standard HTML form POST (no JSON)."""
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    # Check if user exists first
    user = User.query.filter_by(email=email).first()
    
    if user and not user.password_hash:
        # User signed up with Google OAuth
        flash('This account was created with Google Sign-In. Please use the "Sign in with Google" button.', 'error')
        return redirect(url_for('auth'))
    
    # Authenticate with password
    user = AuthService.authenticate(email, password)
    if not user:
        flash('Invalid email or password.', 'error')
        return redirect(url_for('auth'))

    login_user(user, remember=True)  # Enable remember me for persistent sessions
    session.permanent = True
    return redirect(url_for('dashboard'))

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    print(f"Logging out user: {current_user.id}")
    # Set last_seen to past to ensure immediate offline status
    try:
        current_user.last_seen = datetime.utcnow() - timedelta(minutes=15)
        db.session.commit()
    except:
        pass
        
    logout_user()
    session.clear()
    
    # Create response to clear cookies explicitly
    response = redirect(url_for('auth'))
    
    # Clear Flask-Login 'remember me' cookie
    cookie_name = app.config.get('REMEMBER_COOKIE_NAME', 'remember_token')
    response.delete_cookie(cookie_name)
    
    # Clear session cookie
    response.delete_cookie('session')
    
    flash('You have been logged out.', 'success')
    return response

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True)
    print(f"[GOOGLE AUTH] Initiating OAuth flow")
    print(f"[GOOGLE AUTH] Redirect URI: {redirect_uri}")
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def google_callback():
    print(f"[GOOGLE AUTH] Callback received")
    print(f"[GOOGLE AUTH] Request args: {request.args}")
    try:
        print(f"[GOOGLE AUTH] Attempting to authorize access token...")
        token = google.authorize_access_token()
        print(f"[GOOGLE AUTH] Token received successfully")
        user_info = google.parse_id_token(token, nonce=None)
        
        email = user_info.get('email')
        google_id = user_info.get('sub')
        name = user_info.get('name', '')
        picture = user_info.get('picture')

        # Check if user exists
        user = User.query.filter_by(email=email).first()
        is_new_user = False

        if not user:
            is_new_user = True
            # Create new user
            names = name.split(' ', 1) if name else ['', '']
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ''
            
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                google_id=google_id,
                profile_image=picture,
                password_hash=None # No password for Google users
            )
            db.session.add(user)
            db.session.commit()
            
            # Send welcome email to new Google user
            try:
                send_welcome_email(user.email, user.first_name, user.last_name)
            except Exception as e:
                print(f"Failed to send welcome email: {e}")
                # Continue even if email fails
        else:
            # Update existing user info
            if not user.google_id:
                user.google_id = google_id
            if picture:
                user.profile_image = picture
            db.session.commit()

        # Log the user in
        login_user(user, remember=True)
        session.permanent = True
        
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"=" * 80)
        print(f"ERROR during Google Auth:")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {str(e)}")
        print(f"Full Traceback:")
        print(error_details)
        print(f"=" * 80)
        flash(f"Google authentication failed: {str(e)}", "error")
        return redirect(url_for('auth'))

@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    """Handle Google OAuth sign-in from Firebase."""
    import uuid
    
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    email = data.get('email')
    display_name = data.get('displayName', '')
    
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400
    
    # Check if user exists
    user = User.query.filter_by(email=email).first()
    is_new_user = False
    
    if not user:
        is_new_user = True
        # Create new user from Google account
        names = display_name.split(' ', 1) if display_name else ['', '']
        first_name = names[0] if names else ''
        last_name = names[1] if len(names) > 1 else ''
        
        user = User(
            email=email,
            password_hash=generate_password_hash(str(uuid.uuid4())),  # Random password for OAuth users
            first_name=first_name,
            last_name=last_name
        )
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email to new Google user
        try:
            send_welcome_email(user.email, user.first_name, user.last_name)
        except Exception as e:
            print(f"Failed to send welcome email: {e}")
            # Continue even if email fails
    
    # Log in the user
    login_user(user, remember=True)
    session.permanent = True
    
    return jsonify({'status': 'success', 'message': 'Authentication successful'})


@app.route('/dashboard')
@login_required
def dashboard():
    total_todos = Todo.query.filter_by(user_id=current_user.id).count()
    completed_todos = Todo.query.filter_by(user_id=current_user.id, completed=True).count()
    remaining_todos = max(total_todos - completed_todos, 0)

    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_minutes = (
        db.session.query(db.func.coalesce(db.func.sum(StudySession.duration), 0))
        .filter(StudySession.user_id == current_user.id)
        .filter(StudySession.completed_at >= week_ago)
        .scalar()
    )
    weekly_hours = round((weekly_minutes or 0) / 60.0, 1)

    completion_percent = int((completed_todos / total_todos) * 100) if total_todos else 0

    topic_rows = (
        TopicProficiency.query
        .filter_by(user_id=current_user.id)
        .order_by(TopicProficiency.updated_at.desc())
        .limit(6)
        .all()
    )
    avg_proficiency = (
        db.session.query(db.func.coalesce(db.func.avg(TopicProficiency.proficiency), 0))
        .filter(TopicProficiency.user_id == current_user.id)
        .scalar()
    )
    avg_proficiency = int(round(avg_proficiency or 0))
    topics_covered = TopicProficiency.query.filter_by(user_id=current_user.id).count()

    recent_todos = (
        Todo.query
        .filter_by(user_id=current_user.id)
        .order_by(Todo.created_at.desc())
        .limit(5)
        .all()
    )
    upcoming_todos = (
        Todo.query
        .filter_by(user_id=current_user.id, completed=False)
        .order_by(Todo.id.desc())
        .limit(5)
        .all()
    )

    # -------------------------
    # COMPLETED PARENT TASKS
    # (Categories where every subtask is done)
    # -------------------------
    all_user_todos = Todo.query.filter_by(user_id=current_user.id).all()
    cat_map = {}
    for t in all_user_todos:
        cat = t.category if (t.category and t.category.strip()) else None
        if not cat: continue
        if cat not in cat_map:
            cat_map[cat] = []
        cat_map[cat].append(t)
    
    completed_parent_tasks = []
    today_utc = datetime.utcnow()
    start_of_week = today_utc - timedelta(days=today_utc.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    for cat, tasks in cat_map.items():
        if all(tk.completed for tk in tasks):
            # Check if at least one was completed this week
            # Or if it's a recently finished project
            recent_completion = any(tk.completed_at and tk.completed_at >= start_of_week for tk in tasks)
            if recent_completion:
                completed_parent_tasks.append(cat)

    # -------------------------
    # WEEKLY COMPLETED EVENTS
    # -------------------------
    today_date = datetime.utcnow().date()
    start_of_week_date = today_date - timedelta(days=today_date.weekday())
    week_date_strs = [(start_of_week_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    
    completed_events_week = (
        Event.query
        .filter_by(user_id=current_user.id, is_notified=True)
        .filter(Event.date.in_(week_date_strs))
        .order_by(Event.date.desc(), Event.time.desc())
        .all()
    )
    
    
    # Count online users (active in last 5 minutes)
    online_threshold = datetime.utcnow() - timedelta(minutes=5)
    online_users = User.query.filter(User.last_seen >= online_threshold).count()
    # Add at least 1 for current user
    if online_users < 1:
        online_users = 1
    
    # Daily Quests (simple example quests based on user activity)
    quests = []
    # Quest 1: Complete 3 tasks today
    today_completed = Todo.query.filter_by(user_id=current_user.id, completed=True).filter(
        db.func.date(Todo.created_at) == datetime.utcnow().date()
    ).count()
    quests.append({
        'description': 'Complete 3 tasks',
        'icon': 'fa-check-circle',
        'xp_reward': 50,
        'progress': min(today_completed, 3),
        'target': 3,
        'completed': today_completed >= 3
    })
    
    # Quest 2: Study for 30 minutes
    today_study_mins = (
        db.session.query(db.func.coalesce(db.func.sum(StudySession.duration), 0))
        .filter(StudySession.user_id == current_user.id)
        .filter(db.func.date(StudySession.completed_at) == datetime.utcnow().date())
        .scalar()
    ) or 0
    quests.append({
        'description': 'Study for 30 minutes',
        'icon': 'fa-clock',
        'xp_reward': 75,
        'progress': min(today_study_mins, 30),
        'target': 30,
        'completed': today_study_mins >= 30
    })
    
    # Quest 3: Log in daily (always complete if you're seeing this)
    # Quest 3: Log in daily (always complete if you're seeing this)
    quests.append({
        'description': 'Log in today',
        'icon': 'fa-door-open',
        'xp_reward': 25,
        'progress': 1,
        'target': 1,
        'completed': True
    })

    # -------------------------
    # WEEKLY STATS CALCULATION
    # -------------------------
    today = datetime.utcnow().date()
    # Align to current week (Monday - Sunday)
    start_of_week = today - timedelta(days=today.weekday()) 
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    
    daily_stats = []
    total_focus_week = 0
    total_tasks_week = 0
    total_goals_week = 0 
    
    for d in dates:
        # 1. Daily Focus Mins
        d_focus = db.session.query(db.func.sum(StudySession.duration)).filter(
            StudySession.user_id == current_user.id,
            db.func.date(StudySession.completed_at) == d
        ).scalar() or 0
        
        # 2. Daily Tasks Completed (Using real completed_at)
        d_tasks = Todo.query.filter(
            Todo.user_id == current_user.id,
            Todo.completed == True,
            db.func.date(Todo.completed_at) == d
        ).count()
        
        # 3. Daily Goals (High Priority Completed)
        d_goals = Todo.query.filter(
            Todo.user_id == current_user.id,
            Todo.completed == True,
            Todo.priority == 'high',
            db.func.date(Todo.completed_at) == d
        ).count()
        
        total_focus_week += d_focus
        total_tasks_week += d_tasks
        total_goals_week += d_goals
        
        # Normalize for chart (Max 4 hours focus = 100%, Max 5 tasks = 100%)
        focus_pct = min((d_focus / 240) * 100, 100) # 4 hours max bar
        task_pct = min((d_tasks / 5) * 100, 100)    # 5 tasks max bar
        
        daily_stats.append({
            'day': d.strftime('%a'),
            'focus_pct': int(focus_pct),
            'task_pct': int(task_pct),
            'focus_mins': d_focus,
            'task_count': d_tasks
        })

    weekly_stats = {
        'total_focus': total_focus_week,
        'total_tasks': total_tasks_week,
        'total_goals': total_goals_week,
        'chart': daily_stats
    }

    # -------------------------
    # HABIT TRACKER DATA
    # -------------------------
    # Get all active habits
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    
    # Get logged habits for today
    today_logs = HabitLog.query.filter(
        HabitLog.habit_id.in_([h.id for h in habits]),
        HabitLog.completed_date == datetime.utcnow().date()
    ).all()
    today_log_ids = {log.habit_id for log in today_logs}

    # Calculate Weekly Progress (Mon-Sun) - Habit Completion %
    habit_chart = []
    total_habits_count = len(habits)
    
    # -------------------------
    # IMPORTANT ITEMS (For Important Card)
    # -------------------------
    now_ist = datetime.now(IST)
    today_str = now_ist.strftime('%Y-%m-%d')
    time_str = now_ist.strftime('%H:%M')

    # Next event today or in the future (strictly future, not current minute)
    # Handle NULL time by assuming it's an all-day event (so '00:00')
    important_event = Event.query.filter(
        Event.user_id == current_user.id,
        Event.date >= today_str
    ).filter(
        # Logic: If date > today, any time is fine. If date == today, time must be > now OR null (all day)
        db.or_(
            Event.date > today_str,
            db.and_(Event.date == today_str, db.or_(Event.time > time_str, Event.time == None, Event.time == ''))
        )
    ).order_by(Event.date.asc(), Event.time.asc()).first()

    # High priority uncompleted task
    important_todo = Todo.query.filter_by(
        user_id=current_user.id,
        completed=False,
        priority='high'
    ).order_by(Todo.id.desc()).first()

    important_todo_label = "High Priority Task"
    
    # Fallback: If no high priority task, show next due task
    if not important_todo:
        important_todo = Todo.query.filter(
            Todo.user_id == current_user.id,
            Todo.completed == False,
            Todo.due_date != None,
            Todo.due_date >= today_str
        ).order_by(Todo.due_date.asc()).first()
        
        if important_todo:
            important_todo_label = "Upcoming Task"
             

    return render_template(
        'dashboard.html',
        total_todos=total_todos,
        completed_todos=completed_todos,
        remaining_todos=remaining_todos,
        weekly_hours=weekly_hours,
        completion_percent=completion_percent,
        avg_proficiency=avg_proficiency,
        topics_covered=topics_covered,
        topic_rows=topic_rows,
        recent_todos=recent_todos,
        upcoming_todos=upcoming_todos,
        online_users=online_users,
        quests=quests,
        today_study_mins=today_study_mins,
        weekly_stats=weekly_stats,
        habits=habits,
        today_log_ids=today_log_ids,
        habit_chart=habit_chart,
        completed_parent_tasks=completed_parent_tasks,
        completed_events_week=completed_events_week,
        important_event=important_event,
        important_todo=important_todo,
        important_todo_label=important_todo_label
    )

@app.route('/chat')
@login_required
def chat():
    messages = ChatMessage.query.filter_by(user_id=current_user.id, is_group=False).order_by(ChatMessage.created_at.asc()).limit(50).all()
    return render_template('chat.html', chat_messages=messages)

@app.route('/chat/send', methods=['POST'])
@login_required
def chat_send():
    """Personal chat send (AJAX supported)."""
    
    # Handle JSON (AJAX)
    if request.is_json:
        data = request.get_json()
        content = data.get('message', '').strip()
        if not content:
            return jsonify({'status': 'error', 'message': 'Empty message'}), 400
            
        # Store user message
        user_msg = ChatMessage(user_id=current_user.id, role='user', content=content, is_group=False)
        db.session.add(user_msg)
        db.session.commit()

        # Generate AI response (Context Aware)
        reply = ChatService.generate_chat_response(current_user, content)
        
        # Store AI response
        ai_msg = ChatMessage(user_id=current_user.id, role='assistant', content=reply, is_group=False)
        db.session.add(ai_msg)
        db.session.commit()
        
        # Return response with IST timestamps
        return jsonify({
            'status': 'success',
            'reply': reply,
            'user_timestamp': to_ist_time(user_msg.created_at),
            'ai_timestamp': to_ist_time(ai_msg.created_at)
        })


    # Legacy Form Post
    content = request.form.get('message', '').strip()
    if not content:
        return redirect(url_for('chat'))

    # Store user message
    db.session.add(ChatMessage(user_id=current_user.id, role='user', content=content, is_group=False))
    db.session.commit()

    db.session.commit()

    # Generate AI response
    reply = ChatService.personal_reply(current_user, content)
    db.session.add(ChatMessage(user_id=current_user.id, role='assistant', content=reply, is_group=False))
    db.session.commit()

    return redirect(url_for('chat'))

# ----------------------------------------------------
# XP SHOP / GAMIFICATION STORE
# ----------------------------------------------------
class UserItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.String(50), nullable=False) # e.g., 'theme_cyberpunk'
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=False) # For themes/frames that need activation

class ActivePowerUp(db.Model):
    """Track active power-ups with duration and effects"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    power_up_id = db.Column(db.String(50), nullable=False)  # e.g., 'xp_boost', 'mega_xp_boost'
    activated_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # None for instant effects
    multiplier = db.Column(db.Float, default=1.0)  # For XP/time multipliers
    is_active = db.Column(db.Boolean, default=True)
    
    def is_expired(self):
        """Check if power-up has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

class ShopService:
    # Hardcoded catalog for now
    ITEMS = {
        # === THEMES ===
        'theme_neon_city': {
            'id': 'theme_neon_city',
            'name': 'Neon City Theme 🌃',
            'description': 'Urban neon lights cityscape.',
            'price': 3800,
            'icon': 'fa-city',
            'type': 'theme',
            'color': '#06b6d4'
        },
        'theme_sakura': {
            'id': 'theme_sakura',
            'name': 'Sakura Theme 🌸',
            'description': 'Cherry blossom pink serenity.',
            'price': 2800,
            'icon': 'fa-spa',
            'type': 'theme',
            'color': '#f9a8d4'
        },
        'theme_cyberpunk': {
            'id': 'theme_cyberpunk',
            'name': 'Cyberpunk Theme 🤖',
            'description': 'Neon purple visuals and glitch effects.',
            'price': 4000,
            'icon': 'fa-vr-cardboard',
            'type': 'theme',
            'color': '#d946ef'
        },
        'theme_synthwave': {
            'id': 'theme_synthwave',
            'name': 'Synthwave Theme 🎵',
            'description': '80s retro neon grid aesthetic.',
            'price': 3500,
            'icon': 'fa-compact-disc',
            'type': 'theme',
            'color': '#f472b6'
        },
         'theme_aurora': {
            'id': 'theme_aurora',
            'name': 'Aurora Theme 🌌',
            'description': 'Northern lights with flowing colors.',
            'price': 3000,
            'icon': 'fa-wand-magic-sparkles',
            'type': 'theme',
            'color': '#a78bfa'
        },
        
        # === FRAMES ===
        'frame_gold': {
            'id': 'frame_gold',
            'name': 'Golden Frame 🏆',
            'description': 'Shiny gold border with pulsing glow.',
            'price': 2500,
            'icon': 'fa-crown',
            'type': 'frame',
            'color': '#eab308'
        },
        'frame_diamond': {
            'id': 'frame_diamond',
            'name': 'Diamond Frame 💎',
            'description': 'Sparkling diamond border with shimmer.',
            'price': 7500,
            'icon': 'fa-gem',
            'type': 'frame',
            'color': '#a78bfa'
        },
        'frame_fire': {
            'id': 'frame_fire',
            'name': 'Fire Frame 🔥',
            'description': 'Blazing flames surrounding your avatar.',
            'price': 4000,
            'icon': 'fa-fire',
            'type': 'frame',
            'color': '#f97316'
        },
        'frame_ice': {
            'id': 'frame_ice',
            'name': 'Ice Frame ❄️',
            'description': 'Frozen crystal border with frost effect.',
            'price': 3500,
            'icon': 'fa-snowflake',
            'type': 'frame',
            'color': '#38bdf8'
        },
        'frame_glitch': {
            'id': 'frame_glitch',
            'name': 'Glitched Frame 👾',
            'description': 'Animated glitch effect with RGB split.',
            'price': 5000,
            'icon': 'fa-bug',
            'type': 'frame',
            'color': '#ef4444'
        }
    }

    @staticmethod
    def buy_item(user: User, item_id: str):
        item = ShopService.ITEMS.get(item_id)
        if not item:
            return {'status': 'error', 'message': 'Item not found.'}
        
        # Check ownership (unless consumable)
        if item['type'] != 'consumable':
            owned = UserItem.query.filter_by(user_id=user.id, item_id=item_id).first()
            if owned:
                return {'status': 'error', 'message': 'You already own this item!'}

        # Check funds
        if user.total_xp < item['price']:
            needed = item['price'] - user.total_xp
            return {'status': 'error', 'message': f"Short on funds! You need {needed} more XP to unlock this."}

        # Deduct XP
        user.total_xp -= item['price']
        
        # Handle Consumables (Power-Ups)
        if item['type'] == 'consumable':
            effect = item.get('effect')
            
            if effect == 'instant_level':
                # Instant Level Up - Add 500 XP to level up
                user.total_xp += 500
                old_level = user.level
                user.level = GamificationService.calculate_level(user.total_xp)
                db.session.commit()
                return {'status': 'success', 'message': f"Level Up! You are now level {user.level}! 🎉", 'new_xp': user.total_xp}
            
            elif effect in ['xp_multiplier', 'mega_xp_multiplier', 'time_multiplier', 'xp_protection']:
                # Duration-based power-ups
                duration = item.get('duration', 86400)  # Default 24 hours
                expires_at = datetime.utcnow() + timedelta(seconds=duration)
                
                # Determine multiplier
                if effect == 'xp_multiplier':
                    multiplier = 2.0
                elif effect == 'mega_xp_multiplier':
                    multiplier = 5.0
                elif effect == 'time_multiplier':
                    multiplier = 2.0
                else:  # xp_protection
                    multiplier = 0.0  # Special case - prevents XP loss
                
                # Create active power-up
                power_up = ActivePowerUp(
                    user_id=user.id,
                    power_up_id=item_id,
                    activated_at=datetime.utcnow(),
                    expires_at=expires_at,
                    multiplier=multiplier,
                    is_active=True
                )
                db.session.add(power_up)
                db.session.commit()
                
                # Calculate hours remaining
                hours = duration / 3600
                return {'status': 'success', 'message': f"{item['name']} activated! Effect lasts for {int(hours)} hours. ⚡", 'new_xp': user.total_xp}
            
            else:
                # Unknown effect - just store as item
                new_item = UserItem(user_id=user.id, item_id=item_id)
                db.session.add(new_item)
                db.session.commit()
                return {'status': 'success', 'message': f"Purchased {item['name']}!", 'new_xp': user.total_xp}
        
        # Handle Themes and Frames
        new_item = UserItem(user_id=user.id, item_id=item_id)
        db.session.add(new_item)
        db.session.commit()
        
        return {'status': 'success', 'message': f"Purchased {item['name']}!", 'new_xp': user.total_xp}

    @staticmethod
    def equip_item(user: User, item_id: str):
        item = ShopService.ITEMS.get(item_id)
        if not item:
            return {'status': 'error', 'message': 'Item not found.'}

        # Verify ownership
        owned = UserItem.query.filter_by(user_id=user.id, item_id=item_id).first()
        if not owned:
            return {'status': 'error', 'message': 'You do not own this item.'}

        # Handle Equipping based on type
        if item['type'] == 'theme':
            # Unequip other themes
            current_active = (
                db.session.query(UserItem)
                .filter(UserItem.user_id == user.id, UserItem.is_active == True)
                .all()
            )
            
            # Deactivate other themes
            for active_item in current_active:
                # check if it's a theme by looking up the ID in ITEMS (simplified)
                # In real app, we'd store type in DB or join with Item table.
                # Here we check the hardcoded catalog.
                cat_item = ShopService.ITEMS.get(active_item.item_id)
                if cat_item and cat_item['type'] == 'theme':
                    active_item.is_active = False
            
            # Activate new
            owned.is_active = True
            db.session.commit()
            return {'status': 'success', 'message': f"Equipped {item['name']}!"}

        if item['type'] == 'frame':
            # Unequip other frames
            current_active = (
                db.session.query(UserItem)
                .filter(UserItem.user_id == user.id, UserItem.is_active == True)
                .all()
            )
            
            # Deactivate other frames
            for active_item in current_active:
                cat_item = ShopService.ITEMS.get(active_item.item_id)
                if cat_item and cat_item['type'] == 'frame':
                    active_item.is_active = False
            
            # Activate new
            owned.is_active = True
            db.session.commit()
            return {'status': 'success', 'message': f"Equipped {item['name']}!"}

        return {'status': 'error', 'message': 'This item cannot be equipped.'}


@app.route('/shop')
@login_required
def shop():
    # Get user inventory
    inventory = UserItem.query.filter_by(user_id=current_user.id).all()
    owned_ids = {u.item_id for u in inventory}
    active_ids = {u.item_id for u in inventory if u.is_active}
    
    return render_template('shop.html', items=ShopService.ITEMS, owned_ids=owned_ids, active_ids=active_ids)

@app.route('/shop/buy/<item_id>', methods=['POST'])
@login_required
def shop_buy(item_id):
    result = ShopService.buy_item(current_user, item_id)
    if result['status'] == 'success':
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')
    return redirect(url_for('shop'))

@app.route('/shop/equip/<item_id>', methods=['POST'])
@login_required
def shop_equip(item_id):
    result = ShopService.equip_item(current_user, item_id)
    if result['status'] == 'success':
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')
    return redirect(url_for('shop'))

@app.route('/shop/unequip/<item_id>', methods=['POST'])
@login_required
def shop_unequip(item_id):
    # Find the user's item and deactivate it
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
    if user_item:
        user_item.is_active = False
        db.session.commit()
        flash(f'Item unequipped successfully!', 'success')
    else:
        flash('Item not found.', 'error')
    return redirect(url_for('shop'))

@app.route('/group')
@login_required
def group_chat():
    group = GroupService.get_user_group(current_user.id)
    messages = []
    members = []
    online_count = 0
    if group:
        # Load messages and join with User to get names
        messages = (
            GroupChatMessage.query
            .filter_by(group_id=group.id)
            .order_by(GroupChatMessage.created_at.asc())
            .limit(100)
            .all()
        )
        # Join (DBMS concept): membership table join with user table
        members = (
            db.session.query(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .filter(GroupMember.group_id == group.id)
            .all()
        )
        
        # Attach online status (Active within last 5 minutes)
        now = datetime.utcnow()

        for m in members:
            # If last_seen is None, assume offline.
            # 5 minutes threshold
            if m.last_seen and (now - m.last_seen).total_seconds() < 300:
                m.is_online_status = True
                online_count += 1
            else:
                m.is_online_status = False

    return render_template('group_chat.html', group=group, group_messages=messages, group_members=members, online_count=online_count)

@app.route('/group/create', methods=['POST'])
@login_required
def group_create():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Group name is required.', 'error')
        return redirect(url_for('group_chat'))

    GroupService.create_group(current_user.id, name)
    return redirect(url_for('group_chat'))

@app.route('/group/join', methods=['POST'])
@login_required
def group_join():
    invite_code = request.form.get('invite_code', '').strip().upper()
    if not invite_code:
        flash('Invite code is required.', 'error')
        return redirect(url_for('group_chat'))

    try:
        GroupService.join_group(current_user.id, invite_code)
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('group_chat'))

@app.route('/group/leave', methods=['POST'])
@login_required
def group_leave():
    """Leave the current group."""
    membership = GroupMember.query.filter_by(user_id=current_user.id).first()
    if membership:
        db.session.delete(membership)
        db.session.commit()
        flash('You have left the group.', 'success')
    return redirect(url_for('group_chat'))

@app.route('/group/send', methods=['POST'])
@login_required
def group_send():
    group = GroupService.get_user_group(current_user.id)
    if not group:
        flash('Join or create a group first.', 'error')
        return redirect(url_for('group_chat'))

    content = request.form.get('message', '').strip()
    if not content:
        return redirect(url_for('group_chat'))

    db.session.add(GroupChatMessage(group_id=group.id, user_id=current_user.id, role='user', content=content))
    db.session.commit()

    # Group AI: trigger if user mentions @StudyVerse
    if '@StudyVerse' in content.lower() or '@assistant' in content.lower():
        reply = ChatService.personal_reply(current_user, content)
        db.session.add(GroupChatMessage(group_id=group.id, user_id=None, role='assistant', content=reply))
        db.session.commit()

    return redirect(url_for('group_chat'))

@app.route('/group/<int:group_id>/messages')
@login_required
def get_group_messages(group_id):
    """Polling endpoint for group messages."""
    # Check membership
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        return jsonify({'error': 'Not a member'}), 403

    since_id = request.args.get('since', 0, type=int)
    
    messages = (
        GroupChatMessage.query
        .filter(GroupChatMessage.group_id == group_id)
        .filter(GroupChatMessage.id > since_id)
        .order_by(GroupChatMessage.created_at.asc())
        .limit(50)
        .all()
    )
    
    # Format messages for JSON
    msg_list = []
    for m in messages:
        sender_name = 'Unknown'
        avatar = None
        if m.role == 'assistant':
            sender_name = 'AI Coach'
        elif m.user:
            sender_name = m.user.first_name
            avatar = m.user.get_avatar(64)
            
        msg_list.append({
            'id': m.id,
            'user_id': m.user_id,
            'username': sender_name,
            'avatar': avatar,
            'content': m.content,
            'file_path': m.file_path,
            'created_at': to_ist_time(m.created_at),
            'role': m.role
        })
        
    return jsonify({'messages': msg_list})

@app.route('/todos')
@login_required
def todos():
    personal = Todo.query.filter_by(user_id=current_user.id, is_group=False).order_by(Todo.created_at.desc()).all()
    group = Todo.query.filter_by(user_id=current_user.id, is_group=True).order_by(Todo.created_at.desc()).all()
    return render_template('todos.html', personal_todos=personal, group_todos=group)

@app.route('/todos/add', methods=['POST'])
@login_required
def todos_add():
    title = request.form.get('title', '').strip()
    is_group = request.form.get('is_group') == '1'
    if not title:
        return redirect(url_for('todos'))

    todo = Todo(
        user_id=current_user.id,
        title=title,
        completed=False,
        priority=request.form.get('priority', 'medium'),
        due_date=request.form.get('due_date'),
        category=request.form.get('category'),
        is_group=is_group,
    )
    db.session.add(todo)
    db.session.commit()
    
    next_url = request.form.get('next') or request.args.get('next')
    if next_url:
        return redirect(next_url)
    return redirect(url_for('todos'))

@app.route('/todos/add_batch', methods=['POST'])
@login_required
def todos_add_batch():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    category = data.get('category', '').strip()
    priority = data.get('priority', 'Medium')
    due_date = data.get('due_date')
    due_time = data.get('due_time') # NEW: Capture time
    is_group = data.get('is_group') == '1' or data.get('is_group') is True
    subtasks = data.get('subtasks', [])

    if not subtasks:
        return jsonify({'error': 'No subtasks provided'}), 400

    created_count = 0
    for sub_title in subtasks:
        sub_title = str(sub_title).strip()
        if not sub_title:
            continue
        
        todo = Todo(
            user_id=current_user.id,
            title=sub_title,
            completed=False,
            priority=priority,
            due_date=due_date,
            due_time=due_time,       # NEW: Save time
            is_notified=False,       # NEW: Reset notification status
            category=category, # The "Task Title" acts as the category/project name
            is_group=is_group,
        )
        db.session.add(todo)
        created_count += 1

    if created_count > 0:
        db.session.commit()
        return jsonify({'status': 'success', 'count': created_count})
    
    return jsonify({'status': 'no_tasks_created'})

@app.context_processor
def inject_gamification():
    if current_user.is_authenticated:
        rank_info = GamificationService.get_rank(current_user.level)
        # XP to next level = 500 * level (simplified based on formula floor(total/500))
        # actually formula is level = floor(total/500) + 1
        # so next level at: level * 500
        next_level_xp = current_user.level * 500
        progress_percent = int(((current_user.total_xp % 500) / 500) * 100)
        
        # Get active theme
        active_theme_item = (
            db.session.query(UserItem)
            .filter_by(user_id=current_user.id, is_active=True)
            .all()
        )
        
        active_theme = None
        active_frame = None
        for u_item in active_theme_item:
             # Find the first active item that is a 'theme'
             cat_item = ShopService.ITEMS.get(u_item.item_id)
             if cat_item and cat_item['type'] == 'theme':
                 active_theme = u_item.item_id
             elif cat_item and cat_item['type'] == 'frame':
                 active_frame = u_item.item_id

        return dict(
            rank_name=rank_info['name'],
            rank_icon=rank_info['icon'],
            rank_color=rank_info['color'],
            next_level_xp=next_level_xp,
            level_progress=progress_percent,
            xp_remaining=next_level_xp - current_user.total_xp,
            active_theme=active_theme,
            active_frame=active_frame
        )
    return dict()

@app.route('/todos/toggle/<int:todo_id>', methods=['POST'])
@login_required
def todos_toggle(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    todo.completed = not todo.completed
    
    # Update timestamp
    if todo.completed:
        todo.completed_at = datetime.utcnow()
    else:
        todo.completed_at = None
    
    # Award XP if completing
    if todo.completed:
        GamificationService.add_xp(current_user.id, 'task', 10)
        flash('Task completed! +10 XP', 'success')
        
        # Update Topic Proficiency
        if todo.category:
            topic = TopicProficiency.query.filter_by(user_id=current_user.id, topic_name=todo.category).first()
            if not topic:
                topic = TopicProficiency(user_id=current_user.id, topic_name=todo.category, proficiency=0)
                db.session.add(topic)
            topic.proficiency += 10
            topic.updated_at = datetime.utcnow()
            
    else:
        # Deduct XP if unchecked
        GamificationService.add_xp(current_user.id, 'task_undo', -10, force_deduct=True)
        flash('Task unchecked. -10 XP', 'info')

        # Deduct Proficiency if unchecked
        if todo.category:
            topic = TopicProficiency.query.filter_by(user_id=current_user.id, topic_name=todo.category).first()
            if topic and topic.proficiency >= 10:
                topic.proficiency -= 10

    db.session.commit()
    
    next_url = request.form.get('next') or request.args.get('next')
    if next_url:
        return redirect(next_url)

    return redirect(url_for('todos'))

@app.route('/todos/delete/<int:todo_id>', methods=['POST'])
@login_required
def todos_delete(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()

    # DS concept: push deleted item into undo stack stored in session
    undo_stack = session.get('todo_undo_stack', [])
    undo_stack.append({
        'title': todo.title,
        'priority': todo.priority,
        'due_date': todo.due_date,
        'category': todo.category,
        'is_group': bool(todo.is_group),
    })
    session['todo_undo_stack'] = undo_stack[-20:]  # cap stack size

    db.session.delete(todo)
    db.session.commit()

    next_url = request.form.get('next') or request.args.get('next')
    if next_url:
        return redirect(next_url)

    return redirect(url_for('todos'))

@app.route('/todos/undo', methods=['POST'])
@login_required
def todos_undo():
    undo_stack = Stack()
    for item in session.get('todo_undo_stack', []):
        undo_stack.push(item)

    last = undo_stack.pop()
    if last is None:
        return redirect(url_for('todos'))

    # Write the updated stack back to session
    remaining = []
    while not undo_stack.is_empty():
        remaining.append(undo_stack.pop())
    session['todo_undo_stack'] = list(reversed(remaining))

    db.session.add(Todo(
        user_id=current_user.id,
        title=last['title'],
        completed=False,
        priority=last.get('priority', 'medium'),
        due_date=last.get('due_date'),
        category=last.get('category'),
        is_group=last.get('is_group', False),
    ))
    db.session.commit()
    return redirect(url_for('todos'))

@app.route('/pomodoro')
@login_required
def pomodoro():
    return render_template('pomodoro.html')

@app.route('/pomodoro/sessions', methods=['POST'])
@login_required
def pomodoro_save_session():
    """Save completed Pomodoro session to database."""
    duration = request.form.get('duration', type=int)
    mode = request.form.get('mode', 'focus')
    
    if duration:
        study_session = StudySession(
            user_id=current_user.id,
            duration=duration,
            mode=mode,
            completed_at=datetime.utcnow()
        )
        db.session.add(study_session)
        
        # Award XP: 1 XP per minute of focus
        if mode == 'focus':
            # Check for Double Time power-up to adjust stored duration
            active_time_boost = ActivePowerUp.query.filter_by(
                user_id=current_user.id, 
                power_up_id='double_time',
                is_active=True
            ).first()
            
            if active_time_boost and not active_time_boost.is_expired():
                study_session.duration = duration * 2
                xp_amount = duration # add_xp will handle the multiplier
            else:
                xp_amount = duration
                
            result = GamificationService.add_xp(current_user.id, 'focus', xp_amount)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Session saved'})
    
    return jsonify({'status': 'error', 'message': 'Invalid duration'}), 400

@app.route('/pomodoro/goals', methods=['GET'])
@login_required
def pomodoro_get_goals():
    """Fetch session goals (Todos with category='Session Goal')."""
    goals = Todo.query.filter_by(user_id=current_user.id, category='Session Goal').order_by(Todo.created_at.asc()).all()
    return jsonify([
        {
            'id': g.id,
            'title': g.title,
            'completed': g.completed
        } for g in goals
    ])

@app.route('/pomodoro/goals', methods=['POST'])
@login_required
def pomodoro_add_goal():
    """Add a new session goal."""
    data = request.get_json()
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    goal = Todo(
        user_id=current_user.id,
        title=title,
        completed=False,
        category='Session Goal',
        priority='medium',
        is_group=False
    )
    db.session.add(goal)
    db.session.commit()
    
    return jsonify({
        'id': goal.id,
        'title': goal.title,
        'completed': goal.completed
    })

@app.route('/pomodoro/goals/<int:goal_id>/toggle', methods=['POST'])
@login_required
def pomodoro_toggle_goal(goal_id):
    """Toggle completion status of a session goal."""
    goal = Todo.query.filter_by(id=goal_id, user_id=current_user.id, category='Session Goal').first_or_404()
    goal.completed = not goal.completed
    
    if goal.completed:
        # Mini reward for session goals
        GamificationService.add_xp(current_user.id, 'session_goal', 5)
        
    db.session.commit()
    return jsonify({'status': 'success', 'completed': goal.completed})

@app.route('/pomodoro/goals/<int:goal_id>/update', methods=['POST'])
@login_required
def pomodoro_update_goal(goal_id):
    """Update title of a session goal."""
    goal = Todo.query.filter_by(id=goal_id, user_id=current_user.id, category='Session Goal').first_or_404()
    
    data = request.get_json()
    new_title = data.get('title', '').strip()
    
    if new_title:
        goal.title = new_title
        db.session.commit()
        return jsonify({'status': 'success', 'title': goal.title})
    
    return jsonify({'error': 'Empty title'}), 400

@app.route('/pomodoro/goals/<int:goal_id>/delete', methods=['POST'])
@login_required
def pomodoro_delete_goal(goal_id):
    """Delete a session goal."""
    goal = Todo.query.filter_by(id=goal_id, user_id=current_user.id, category='Session Goal').first_or_404()
    db.session.delete(goal)
    db.session.commit()
    return jsonify({'status': 'success'})

# -------------------------
# HABIT TRACKER ROUTES
# -------------------------
@app.route('/habits/add', methods=['POST'])
@login_required
def habits_add():
    title = request.form.get('title', '').strip()
    if title:
        habit = Habit(user_id=current_user.id, title=title)
        db.session.add(habit)
        db.session.commit()
        flash('Habit added!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/habits/toggle/<int:habit_id>', methods=['POST'])
@login_required
def habits_toggle(habit_id):
    habit = Habit.query.filter_by(id=habit_id, user_id=current_user.id).first_or_404()
    today = datetime.utcnow().date()
    
    # Check if logged for today
    log = HabitLog.query.filter_by(habit_id=habit.id, completed_date=today).first()
    
    if log:
        # Uncheck
        db.session.delete(log)
        db.session.commit()
    else:
        # Check
        log = HabitLog(habit_id=habit.id, completed_date=today)
        db.session.add(log)
        db.session.commit()
        
        # Gamification: Small XP for habit
        GamificationService.add_xp(current_user.id, 'habit', 5)

    return redirect(url_for('dashboard'))

@app.route('/habits/delete/<int:habit_id>', methods=['GET'])
@login_required
def habits_delete(habit_id):
    habit = Habit.query.filter_by(id=habit_id, user_id=current_user.id).first_or_404()
    # Logs cascade delete would be better, but manual verify
    HabitLog.query.filter_by(habit_id=habit.id).delete()
    db.session.delete(habit)
    db.session.commit()
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/api/habits/stats', methods=['GET'])
@login_required
def api_habit_stats():
    """Return this week's habit completion for the chart."""
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday()) # Monday
    
    # Get all user habits
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    total_habits = len(habits)
    
    stats = []
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    if total_habits == 0:
        # Return empty stats if no habits
        for i in range(7):
            stats.append({'day': days[i], 'pct': 0})
        return jsonify(stats)

    for i in range(7):
        date_obj = start_of_week + timedelta(days=i)
        date_only = date_obj.date()
        
        # Count logs on this day for user's habits
        # Join HabitLog with Habit to ensure it belongs to user
        logs_count = (
            HabitLog.query
            .join(Habit)
            .filter(Habit.user_id == current_user.id)
            .filter(HabitLog.completed_date == date_only)
            .count()
        )
        
        pct = int((logs_count / total_habits) * 100)
        stats.append({
            'day': days[i],
            'pct': pct,
            'date': date_only.isoformat()
        })
        
    return jsonify(stats)


@app.route('/habit-debugger')
@login_required
def habit_debugger():
    return render_template('habit-debugger.html')

@app.route('/syllabus')
@app.route('/syllabus/<int:view_id>')
@login_required
def syllabus(view_id=None):
    # Get all docs sorted by newest first
    all_docs = SyllabusDocument.query.filter_by(user_id=current_user.id).order_by(SyllabusDocument.created_at.desc()).all()
    
    if not all_docs:
        doc = None
        archived_docs = []
    else:
        # If view_id is provided, find that doc
        if view_id:
            doc = next((d for d in all_docs if d.id == view_id), None)
            # If not found (unauthorized?), fallback to newest
            if not doc:
                doc = all_docs[0]
        else:
            # Default to newest (Active)
            doc = all_docs[0]
            
        # Archived are all except the one currently being viewed? 
        # Or archived are purely the "non-newest" ones?
        # Let's say: Archived list contains ALL docs except the current one being viewed, to allow switching.
        archived_docs = [d for d in all_docs if d.id != doc.id]

    # TODO: We really should filter chapters/todos by the specific syllabus!
    # currently `build_chapters_from_todos` fetches ALL tasks.
    # We need to link tasks to a syllabus_id or category matching the syllabus filename.
    # For now, to keep it simple as requested:
    # We will assume "Categories" == "Syllabus Name" or just display all.
    # Since the user asked for "completed courses section", we might need to filter tasks.
    # Given the current simple data model where tasks are just "Todos" with categories:
    # We will just show the current state.
    # Pass the ID of the specific syllabus we are viewing
    current_view_id = doc.id if doc else None
    
    chapters = SyllabusService.build_chapters_from_todos(current_user.id, syllabus_id=current_view_id)
    total_topics = sum(c['total'] for c in chapters)
    completed_topics = sum(c['completed'] for c in chapters)
    avg_completion = int((completed_topics / total_topics) * 100) if total_topics else 0
    
    return render_template(
        'syllabus.html',
        syllabus_doc=doc,
        archived_docs=archived_docs,
        chapters=chapters,
        chapters_count=len(chapters),
        topics_count=total_topics,
        completed_count=completed_topics,
        avg_completion=avg_completion,
    )

@app.route('/syllabus/restore/<int:doc_id>', methods=['POST'])
@login_required
def syllabus_restore(doc_id):
    """Restore an archived syllabus by making it the most recent."""
    doc = SyllabusDocument.query.get_or_404(doc_id)
    if doc.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('syllabus'))
    
    # Update its created_at to now to make it 'current'
    doc.created_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'Restored {doc.filename} as active syllabus.', 'success')
    return redirect(url_for('syllabus'))

@app.route('/syllabus/upload', methods=['POST'])
@login_required
def syllabus_upload():
    """Upload and extract PDF syllabus."""
    uploaded = request.files.get('pdf')
    if not uploaded:
        flash('Please select a PDF file.', 'error')
        return redirect(url_for('syllabus'))

    filename = uploaded.filename or 'syllabus.pdf'

    pdf_bytes = uploaded.read()
    if not pdf_bytes:
        flash('Uploaded PDF was empty.', 'error')
        return redirect(url_for('syllabus'))

    # AI: Extract tasks directly from the PDF using Gemini (real API).
    tasks = []
    try:
        tasks = SyllabusService.extract_tasks_from_pdf(pdf_bytes)
    except Exception as e:
        flash(f'AI task extraction failed: {str(e)}', 'error')

    # Extract text with PyPDF2 (used as context for chat). Some PDFs (scans) may yield no text.
    extracted = ""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            text = page.extract_text() or ''
            parts.append(text)
        extracted = "\n".join(parts).strip()
    except Exception:
        extracted = ""

    if not extracted:
        # Keep a non-empty placeholder because SyllabusDocument.extracted_text is NOT NULL.
        extracted = f"(No text could be extracted from this PDF. It may be a scanned document.)\nFilename: {filename}"
        flash('PDF uploaded, but no text could be extracted (might be scanned image). Tasks can still be generated by AI.', 'error')

    doc = SyllabusService.save_syllabus(current_user.id, filename, extracted)

    # Persist AI-generated tasks into real Todos.
    target_date_str = request.form.get('target_date')
    target_date = None
    days_diff = 1
    
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
            today = datetime.now()
            days_diff = (target_date - today).days
            if days_diff <= 0:
                 days_diff = 1 # Minimum 1 day
        except ValueError:
            pass

    # Count total items to be created for distribution
    total_items = 0
    if tasks:
        for task in tasks:
            total_items += 1 # Chapter task
            total_items += len(task.get("subtasks", []))
            
    items_per_day = 1
    if total_items > 0 and days_diff > 0:
        import math
        items_per_day = math.ceil(total_items / days_diff)

    completed_items_count = 0
    created_count = 0
    
    if tasks:
        for task in tasks:
            chapter = str(task.get("title", "")).strip() or "Chapter"
            subtasks = task.get("subtasks", [])
            chapter_category = chapter[:50]

            # Calculate Due Date
            day_offset = completed_items_count // items_per_day
            due_date_obj = datetime.now() + timedelta(days=day_offset)
            due_date_str = due_date_obj.strftime('%Y-%m-%d') if target_date else None

            # Create a parent todo for the chapter
            chapter_title = chapter[:200]
            exists = Todo.query.filter_by(user_id=current_user.id, title=chapter_title, category=chapter_category, is_group=False).first()
            if not exists:
                db.session.add(Todo(
                    user_id=current_user.id,
                    title=chapter_title,
                    completed=False,
                    priority='high', # Chapters are main goals
                    due_date=due_date_str,
                    category=chapter_category,
                    is_group=False,
                    syllabus_id=doc.id  # Link to this syllabus
                ))
                created_count += 1
            
            completed_items_count += 1

            if isinstance(subtasks, list):
                for sub in subtasks:
                    sub_title = str(sub).strip()
                    if not sub_title:
                        continue
                    sub_title = sub_title[:200]
                    
                    # Recalculate due date for subtasks as well to distribute them
                    day_offset = completed_items_count // items_per_day
                    due_date_obj = datetime.now() + timedelta(days=day_offset)
                    due_date_str = due_date_obj.strftime('%Y-%m-%d') if target_date else None
                    
                    exists = Todo.query.filter_by(user_id=current_user.id, title=sub_title, category=chapter_category, is_group=False).first()
                    if exists:
                        continue
                    db.session.add(Todo(
                        user_id=current_user.id,
                        title=sub_title,
                        completed=False,
                        priority='medium',
                        due_date=due_date_str,
                        category=chapter_category,
                        is_group=False,
                        syllabus_id=doc.id  # Link to this syllabus
                    ))
                    created_count += 1
                    completed_items_count += 1

        db.session.commit()

    if created_count > 0:
        flash(f'Created {created_count} tasks from PDF using Gemini!', 'success')
    else:
        flash('PDF uploaded and processed successfully!', 'success')
    return redirect(url_for('syllabus'))

@app.route('/api/update_proficiency', methods=['POST'])
@login_required
def update_proficiency():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
        
    topic_name = data.get('topic_name')
    score = data.get('score') # 0-100 or 1-10
    
    if not topic_name or score is None:
        return jsonify({'error': 'Missing fields'}), 400
        
    # Scale 1-10 to 0-100 if needed, assuming input might be 1-10 slider
    try:
        score = int(score)
        if score <= 10:
             score = score * 10
    except:
        return jsonify({'error': 'Invalid score'}), 400

    topic = TopicProficiency.query.filter_by(user_id=current_user.id, topic_name=topic_name).first()
    if not topic:
        topic = TopicProficiency(user_id=current_user.id, topic_name=topic_name, proficiency=score)
        db.session.add(topic)
    else:
        # Simple moving average or just overwrite?
        # User explicitly sets "Confidence", so overwrite or weighted average is best.
        # Let's do a weighted update: current*0.7 + new*0.3
        # Actually, if the user says "I am 8/10 confident", that is the current state. Overwrite.
        topic.proficiency = score
        topic.updated_at = datetime.utcnow()
        
    db.session.commit()
    return jsonify({'status': 'success', 'new_score': topic.proficiency})


@app.route('/api/syllabus_graph')
@login_required
def syllabus_graph():
    """Return JSON data for 3D Force Graph."""
    chapters = SyllabusService.build_chapters_from_todos(current_user.id)
    
    nodes = []
    links = []
    
    # Root Node
    nodes.append({'id': 'My Galaxy', 'group': 0, 'val': 30, 'color': '#ffffff'})
    
    for chapter in chapters:
        cat_name = chapter['name']
        # Chapter Node
        nodes.append({
            'id': cat_name,
            'group': 1,
            'val': 15,
            'color': '#60a5fa' # Blue
        })
        links.append({
            'source': 'My Galaxy',
            'target': cat_name
        })
        
        # Topic Nodes
        for t in chapter['todos']:
            t_title = t.title[:30] + '...' if len(t.title) > 30 else t.title
            
            # Helper to avoid ID collisions if same topic name exists in multiple chapters (unlikely but possible)
            node_id = f"{cat_name} || {t_title}" 
            
            color = '#4ade80' if t.completed else '#f43f5e' # Green or Red
            
            nodes.append({
                'id': node_id,
                # We want to display the clean title, 3d-force-graph uses 'id' as label by default but we can change accessors
                'name': t_title, 
                'group': 2,
                'val': 5,
                'color': color
            })
            links.append({
                'source': cat_name,
                'target': node_id
            })
            
    return jsonify({'nodes': nodes, 'links': links})

@app.route('/progress')
@login_required
def progress():
    total_todos = Todo.query.filter_by(user_id=current_user.id).count()
    completed_todos = Todo.query.filter_by(user_id=current_user.id, completed=True).count()
    completion_percent = int((completed_todos / total_todos) * 100) if total_todos else 0

    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_minutes = (
        db.session.query(db.func.coalesce(db.func.sum(StudySession.duration), 0))
        .filter(StudySession.user_id == current_user.id)
        .filter(StudySession.completed_at >= week_ago)
        .scalar()
    )
    weekly_hours = round((weekly_minutes or 0) / 60.0, 2)
    sessions_week = StudySession.query.filter_by(user_id=current_user.id).filter(StudySession.completed_at >= week_ago).count()

    # Consecutive-day streak based on completed sessions.
    streak = 0
    # Calculate Monday of the current week
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday()) # Monday = 0
    
    daily = []
    max_hours = 0.0
    
    # Iterate Mon (0) to Sun (6)
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        start_dt = datetime.combine(day, datetime.min.time())
        end_dt = datetime.combine(day, datetime.max.time())
        
        minutes = (
            db.session.query(db.func.coalesce(db.func.sum(StudySession.duration), 0))
            .filter(StudySession.user_id == current_user.id)
            .filter(StudySession.completed_at >= start_dt)
            .filter(StudySession.completed_at <= end_dt)
            .scalar()
        )
        hours = round((minutes or 0) / 60.0, 2)
        max_hours = max(max_hours, hours)
        
        # Format label (e.g. "1.5h" or "45m")
        total_minutes = int(minutes or 0)
        display_val = ""
        if total_minutes > 0:
            if total_minutes < 60:
                display_val = f"{total_minutes}m"
            else:
                h = total_minutes // 60
                m = total_minutes % 60
                display_val = f"{h}h {m}m" if m > 0 else f"{h}h"
                
        daily.append({
            'label': day.strftime('%a'),
            'hours': hours,
            'minutes': total_minutes,
            'display': display_val,
            'is_future': day > today
        })

    for d in daily:
        # Use minutes for more precise percentage relative to max
        max_minutes = max([x['minutes'] for x in daily]) if daily else 0
        
        if max_minutes > 0:
            d['percent'] = int((d['minutes'] / max_minutes) * 100)
            if d['minutes'] > 0 and d['percent'] < 5:
                d['percent'] = 5
        else:
            d['percent'] = 0

    top_topics = (
        TopicProficiency.query
        .filter_by(user_id=current_user.id)
        .order_by(TopicProficiency.proficiency.desc())
        .limit(5)
        .all()
    )
    
    # Fetch user inventory count for streak freezes
    streak_freezes = UserItem.query.filter_by(user_id=current_user.id, item_id='streak_freeze').count()

    # Category Distribution for Pie Chart
    categories = db.session.query(Todo.category, db.func.count(Todo.id))\
        .filter(Todo.user_id == current_user.id)\
        .group_by(Todo.category).all()
    category_data = {cat or 'Uncategorized': count for cat, count in categories}

    return render_template(
        'progress.html',
        total_todos=total_todos,
        completed_todos=completed_todos,
        completion_percent=completion_percent,
        weekly_hours=weekly_hours,
        sessions_week=sessions_week,
        day_streak=streak,
        daily_hours=daily,
        top_topics=top_topics,
        streak_freezes=streak_freezes,
        category_distribution=category_data
    )

@app.route('/leaderboard')
@login_required
def leaderboard():
    """Global leaderboard based on level and XP."""
    # Get top 50 users ordered by level (desc), then by total_xp (desc)
    top_users = (
        User.query
        .filter(User.is_public_profile == True)
        .order_by(User.level.desc(), User.total_xp.desc())
        .limit(50)
        .all()
    )
    
    # Calculate current user's rank much more efficiently
    # Rank is 1 + number of users who have more level OR same level but more XP
    my_rank = User.query.filter(
        User.is_public_profile == True,
        db.or_(
            User.level > current_user.level,
            db.and_(
                User.level == current_user.level,
                User.total_xp > current_user.total_xp
            )
        )
    ).count() + 1
    
    return render_template(
        'leaderboard.html',
        leaderboard=top_users,
        my_rank=my_rank
    )

@app.route('/settings')
@login_required
def settings():
    return profile(current_user.id)

@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # Ensure badges are up to date
    GamificationService.check_badges(user)
    db.session.commit()
    
    badges = UserBadge.query.filter_by(user_id=user.id).all()
    # Calculate stats for the target user
    total_focus_minutes = db.session.query(db.func.sum(StudySession.duration))\
        .filter(StudySession.user_id == user.id).scalar() or 0
    total_focus_hours = round(total_focus_minutes / 60, 1)

    # Fetch tasks for Calendar (only if viewing own profile)
    calendar_events = []
    if current_user.is_authenticated and user.id == current_user.id:
        calendar_events = Todo.query.filter_by(user_id=user.id, completed=False)\
            .filter(Todo.due_date.isnot(None))\
            .filter(Todo.due_date != '')\
            .order_by(Todo.due_date.asc())\
            .all()

    # Get Active Frame
    active_frame = None
    active_items = UserItem.query.filter_by(user_id=user.id, is_active=True).all()
    for u_item in active_items:
        cat_item = ShopService.ITEMS.get(u_item.item_id)
        if cat_item and cat_item['type'] == 'frame':
            active_frame = cat_item
            break

    return render_template('profile.html', user=user, badges=badges, total_focus_hours=total_focus_hours, calendar_events=calendar_events, active_frame=active_frame)

@app.route('/calendar')
@login_required
def calendar_view():
    # Only show uncompleted tasks with due dates for the calendar
    calendar_events = Todo.query.filter_by(user_id=current_user.id, completed=False)\
        .filter(Todo.due_date.isnot(None))\
        .filter(Todo.due_date != '')\
        .order_by(Todo.due_date.asc())\
        .all()
    
    return render_template('calendar.html', calendar_events=calendar_events)

@app.route('/settings/public-profile', methods=['POST'])
@login_required
def update_public_profile():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    is_public = data.get('is_public', True)
    current_user.is_public_profile = bool(is_public)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route('/settings/update', methods=['POST'])
@login_required
def settings_update():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400

    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip().lower()

    if not first_name or not email:
        return jsonify({'status': 'error', 'message': 'First Name and Email are required'}), 400

    # formatting check for email could go here

    current_user.first_name = first_name
    current_user.last_name = last_name
    
    # Check if email is being changed and if it's taken
    if email != current_user.email:
        existing = User.query.filter_by(email=email).first()
        if existing:
            return jsonify({'status': 'error', 'message': 'Email already in use'}), 400
        current_user.email = email
    current_user.about_me = data.get('about_me', current_user.about_me)

    try:
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Profile updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# NOTE: We intentionally avoid JSON-based API endpoints for this semester project.






# ------------------------------
# SocketIO & Real-time Logic
# ------------------------------

@socketio.on('join')
def on_join(data):
    group_id = data.get('group_id')
    if group_id:
        room_name = str(group_id)
        join_room(room_name)
        print(f"✓ User {current_user.id if current_user.is_authenticated else 'Unknown'} joined room {room_name}")
        # Send confirmation back to THIS client only
        emit('joined_room', {'room': room_name})

@socketio.on('send_message')
def handle_message(data):
    group_id = data.get('group_id')
    content = data.get('content', '')
    file_path = data.get('file_path')
    
    if not group_id or not current_user.is_authenticated:
        return

    # Check membership
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        return

    msg = GroupChatMessage(
        group_id=group_id,
        user_id=current_user.id,
        role='user',
        content=content,
        file_path=file_path
    )
    db.session.add(msg)
    db.session.commit()

    # Convert timestamp to IST
    ist_time = to_ist_time(msg.created_at)
    
    message_data = {
        'id': msg.id,
        'user_id': current_user.id,
        'username': current_user.first_name or 'User',
        'content': msg.content,
        'file_path': msg.file_path,
        'created_at': ist_time,
        'role': 'user'
    }

    # Broadcast to everyone in the room
    print(f"📤 Broadcasting message to room {group_id}: {msg.content[:50]}")
    emit('receive_message', message_data, room=str(group_id), broadcast=True)
    print(f"✅ Message broadcasted")

    
    # AI Logic (Simple mention check)
    if '@StudyVerse' in content.lower() or '@assistant' in content.lower():
        reply = ChatService.personal_reply(current_user, content)
        ai_msg = GroupChatMessage(group_id=group_id, user_id=None, role='assistant', content=reply)
        db.session.add(ai_msg)
        db.session.commit()
        
        # Convert AI message timestamp to IST
        ai_ist_time = to_ist_time(ai_msg.created_at)
        
        socketio.emit('receive_message', {
            'id': ai_msg.id,
            'user_id': None,
            'username': 'StudyVerse',
            'content': ai_msg.content,
            'created_at': ai_ist_time,
            'role': 'assistant'
        }, room=str(group_id), include_self=True)


@app.route('/group/upload', methods=['POST'])
@login_required
def group_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(save_path)
    
    return jsonify({
        'url': url_for('static', filename=f'uploads/{unique_filename}'),
        'filename': filename
    })

@app.route('/profile/upload_cover', methods=['POST'])
@login_required
def profile_upload_cover():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        # Use timestamp to avoid caching issues
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_filename = f"cover_{current_user.id}_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(save_path)
        
        # Update user profile
        current_user.cover_image = f"uploads/{unique_filename}"
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'url': url_for('static', filename=f'uploads/{unique_filename}')
        })
    
    return jsonify({'error': 'Upload failed'}), 500

# ------------------------------
# BYTE BATTLE LOGIC (1v1 AI Referee)
# ------------------------------

@app.route('/battle')
@login_required
def battle():
    return render_template('battle.html')

# In-memory battle state
battles = {}

def generate_room_code(length=4):
    import random, string
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        if code not in battles:
            return code

@socketio.on('battle_create')
def on_battle_create(data):
    if not current_user.is_authenticated:
        return
    
    room_code = generate_room_code()
    battles[room_code] = {
        'host': current_user.id,
        'players': {
            current_user.id: {
                'name': current_user.first_name or 'Player 1',
                'sid': request.sid,
                'joined_at': datetime.utcnow()
            }
        },
        'state': 'waiting', # waiting, setup, battle, judging, result
        'config': {'difficulty': None, 'language': None},
        'problem': None,
        'submissions': {},
        'rematch_votes': {}, # player_id: "yes"/"no"
        'pending_join': None # Stores info about player requesting to join
    }
    
    join_room(room_code)
    emit('battle_created', {'room_code': room_code, 'player_id': current_user.id})
    print(f"Battle created: {room_code} by {current_user.first_name}")

@socketio.on('battle_rejoin_attempt')
def on_battle_rejoin_attempt(data):
    if not current_user.is_authenticated:
        return
        
    room_code = data.get('room_code', '').strip().upper()
    if room_code not in battles:
        emit('battle_error', {'message': 'Room invalid or expired.'})
        return
        
    room = battles[room_code]
    
    # Verify user is actually in the room
    if current_user.id in room['players']:
        # UPDATE SID (Critical for refresh)
        room['players'][current_user.id]['sid'] = request.sid
        
        join_room(room_code)
        
        # Determine if host
        is_host = (room['host'] == current_user.id)
        
        emit('battle_rejoined', {
            'state': room['state'], 
            'room_code': room_code,
            'is_host': is_host,
            'players': [{'id': p, 'name': v['name']} for p,v in room['players'].items()]
        })
        print(f"User {current_user.first_name} re-joined room {room_code}")
    else:
        # User thinks they are in room, but server disagrees (restart)
        emit('battle_error', {'message': 'You are not in this room.'})

@socketio.on('battle_join_request')
def on_battle_join_request(data):
    if not current_user.is_authenticated:
        return
        
    room_code = data.get('room_code', '').strip().upper()
    if room_code not in battles:
        emit('battle_error', {'message': 'Invalid room code.'})
        return
        
    room = battles[room_code]
    if len(room['players']) >= 2:
        emit('battle_error', {'message': 'Room is full.'})
        return

    # Check if already in (re-join)
    if current_user.id in room['players']:
        room['players'][current_user.id]['sid'] = request.sid
        join_room(room_code)
        emit('battle_rejoined', {'state': room['state'], 'room_code': room_code})
        return

    # Store pending request
    room['pending_join'] = {
        'id': current_user.id,
        'name': current_user.first_name or 'Opponent',
        'sid': request.sid
    }
    
    # Notify Host - Broadcast to room AND specifically to host's SID
    # This ensures the notification reaches the host even after page refresh
    host_sid = room['players'][room['host']]['sid']
    
    # Emit to host's specific session
    socketio.emit('battle_join_request_notify', {
        'player_name': room['pending_join']['name']
    }, room=host_sid)
    
    # Also broadcast to entire room as backup
    socketio.emit('battle_join_request_notify', {
        'player_name': room['pending_join']['name']
    }, room=room_code)

@socketio.on('battle_join_response')
def on_battle_join_response(data):
    room_code = data.get('room_code')
    accepted = data.get('accepted')
    
    if not room_code or room_code not in battles:
        return
    
    room = battles[room_code]
    # Only host can accept
    if current_user.id != room['host']:
        return
        
    pending = room.get('pending_join')
    if not pending:
        return
        
    if accepted:
        # Add player
        room['players'][pending['id']] = {
            'name': pending['name'],
            'sid': pending['sid'],
            'joined_at': datetime.utcnow()
        }
        
        # Manually join the socket room for the new player
        # Note: In Flask-SocketIO, we can't easily force another SID to join a room 
        # unless we are in that context or use a specific manager. 
        # Easier approach: Emit 'join_accepted' to the pending player, they emit 'battle_confirm_join'.
        socketio.emit('join_accepted', {'room_code': room_code}, room=pending['sid'])
        room['pending_join'] = None
    else:
        socketio.emit('battle_error', {'message': 'Host rejected your request.'}, room=pending['sid'])
        room['pending_join'] = None

@socketio.on('battle_confirm_join')
def on_battle_confirm_join(data):
    room_code = data.get('room_code')
    if room_code in battles and current_user.id in battles[room_code]['players']:
        join_room(room_code)
        
        # Room is full, move to SETUP immediately
        room = battles[room_code]
        room['state'] = 'setup'
        
        # Notify both to open UI
        emit('battle_entered', {'room_code': room_code}, room=room_code)
        
        # AI Welcome Message
        socketio.emit('battle_chat_message', {
            'sender': 'ByteBot',
            'message': (
                "Welcome to Byte Battle ⚔️\n"
                "Both players are connected.\n\n"
                f"Host ({room['players'][room['host']]['name']}), please select:\n"
                "• Difficulty: Easy / Medium / Hard\n"
                "• Language: Python / JS / Java / C"
            ),
            'type': 'system'
        }, room=room_code)

@socketio.on('battle_chat_send')
def on_battle_chat_send(data):
    room_code = data.get('room_code')
    message = data.get('message', '').strip()
    
    if not room_code or room_code not in battles:
        return
        
    room = battles[room_code]
    player = room['players'].get(current_user.id)
    if not player:
        return

    # Broadcast user message
    emit('battle_chat_message', {
        'sender': player['name'],
        'message': message,
        'type': 'user'
    }, room=room_code)
    
    # Handle Setup Logic via Chat
    if room['state'] == 'setup':
        if current_user.id == room['host']:
            # Parse settings
            msg_lower = message.lower()
            
            # Difficulty
            if 'easy' in msg_lower: room['config']['difficulty'] = 'Easy'
            elif 'medium' in msg_lower: room['config']['difficulty'] = 'Medium'
            elif 'hard' in msg_lower: room['config']['difficulty'] = 'Hard'
            
            # Language
            if 'python' in msg_lower: room['config']['language'] = 'Python'
            elif 'javascript' in msg_lower or 'js' in msg_lower: room['config']['language'] = 'JavaScript'
            elif 'java' in msg_lower: room['config']['language'] = 'Java'
            elif 'c++' in msg_lower or 'cpp' in msg_lower: room['config']['language'] = 'C++'
            elif 'c' in msg_lower: room['config']['language'] = 'C'
            
            # Check if done
            config = room['config']
            if config['difficulty'] and config['language']:
                room['state'] = 'generating'
                emit('battle_chat_message', {
                    'sender': 'ByteBot',
                    'message': f"Configuration locked: {config['difficulty']} | {config['language']}.\nGenerating problem...",
                    'type': 'system'
                }, room=room_code)
                
                # Start Battle
                socketio.start_background_task(start_battle_task, room_code)
            else:
                 # Feedback on what's missing
                 missing = []
                 if not config['difficulty']: missing.append("Difficulty")
                 if not config['language']: missing.append("Language")
                 if missing:
                      # Only reply if it looked like an attempt (optional, to avoid spam)
                      pass 

def start_battle_task(room_code):
    with app.app_context():
        room = battles[room_code]
        config = room['config']
        
        problem = generate_battle_problem(config['difficulty'], config['language'])
        room['problem'] = problem
        room['state'] = 'battle'
        room['start_time'] = datetime.utcnow().timestamp()
        
        # Announce problem
        socketio.emit('battle_chat_message', {
            'sender': 'ByteBot',
            'message': "Here is your challenge.\nTimer has started.",
            'type': 'system'
        }, room=room_code)
        
        socketio.emit('battle_started', {
            'problem': problem,
            'duration': 600, # 10 mins
            'language': config['language']
        }, room=room_code)

@socketio.on('battle_submit')
def on_battle_submit(data):
    room_code = data.get('room_code')
    code = data.get('code')
    
    if not room_code or room_code not in battles:
        return
        
    room = battles[room_code]
    if room['state'] != 'battle':
        return
        
    # Store submission
    submission_time = datetime.utcnow().timestamp()
    time_taken = submission_time - room.get('start_time', submission_time)
    
    room['submissions'][current_user.id] = {
        'code': code,
        'time_taken': time_taken,
        'player_name': room['players'][current_user.id]['name']
    }
    
    # Notify others
    emit('battle_notification', {'message': f"🔔 {room['players'][current_user.id]['name']} has submitted their solution."}, room=room_code)
    emit('battle_chat_message', {'sender': 'ByteBot', 'message': f"🔔 {room['players'][current_user.id]['name']} has submitted their solution.", 'type': 'system'}, room=room_code)
    
    # Check if all submitted
    if len(room['submissions']) == len(room['players']):
        room['state'] = 'judging'
        emit('battle_state_change', {'state': 'judging'}, room=room_code)
        socketio.start_background_task(judge_battle, room_code)

def generate_battle_problem(difficulty, language):
    prompt = (
        f"Generate a single {difficulty} difficulty coding interview problem suitable for {language}. "
        "Return ONLY valid JSON with this structure: "
        "{ \"title\": \"Problem Title\", \"description\": \"Clear problem statement...\", "
        "\"input_format\": \"Input description...\", \"output_format\": \"Output description...\", "
        "\"example_input\": \"...\", \"example_output\": \"...\" }"
    )
    
    try:
        response = call_ai_api([{'role': 'user', 'content': prompt}])
        # Cleanup JSON
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
            
        return json.loads(response.strip())
    except Exception as e:
        print(f"Error generating problem: {e}")
        return {
            "title": "Palindrome Check",
            "description": "Write a program to check if a string is a palindrome.",
            "input_format": "A single string S.",
            "output_format": "Print 'YES' if palindrome, else 'NO'.",
            "example_input": "racecar",
            "example_output": "YES"
        }

def judge_battle(room_code):
    """Background task to judge the battle"""
    with app.app_context():
        room = battles.get(room_code)
        if not room:
            return

        submissions = list(room['submissions'].values())
        if not submissions:
            return

        problem_desc = json.dumps(room['problem'])
        subs_text = ""
        for i, sub in enumerate(submissions):
            subs_text += f"\nPlayer ({sub['player_name']}) Code [Time: {round(sub['time_taken'],1)}s]:\n{sub['code']}\n"

        prompt = (
            f"You are the referee of a coding battle. Problem: {problem_desc}\n"
            f"Submissions: {subs_text}\n"
            "Evaluate based on: 1. Correctness (Passes all edge cases?) 2. Logic quality 3. Time Taken.\n"
            "Return ONLY valid JSON: "
            "{ \"winner\": \"Player Name\" (or 'Draw'), \"reason\": \"Why they won...\", "
            "\"winner_id\": 123 (user id or null if draw), "
            "\"scores\": { \"Player 1 Name\": 90, \"Player 2 Name\": 85 } }"
        )
        
        # Helper to find user ID by name (AI might not return ID perfectly, so we map names)
        # Actually better to ask AI for index or just rely on name matching?
        # Let's map names to IDs first.
        name_to_id = { p['name']: pid for pid, p in room['players'].items() }
        
        try:
            response = call_ai_api([{'role': 'user', 'content': prompt}])
             # Cleanup JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            result = json.loads(response.strip())
            
            # Award XP
            difficulty = room['config'].get('difficulty', 'Easy')
            xp_map = {'Easy': 100, 'Medium': 500, 'Hard': 1000}
            base_xp = xp_map.get(difficulty, 100)
            
            winner_name = result.get('winner')
            winner_id = name_to_id.get(winner_name)
            
            if winner_id:
                # Winner gets full XP
                GamificationService.add_xp(winner_id, 'battle_win', base_xp)
                result['xp_awarded'] = {winner_name: base_xp}
            elif winner_name == 'Draw':
                # Both get 50%
                half_xp = int(base_xp * 0.5)
                xp_dict = {}
                for pid in room['players']:
                    GamificationService.add_xp(pid, 'battle_draw', half_xp)
                    pname = room['players'][pid]['name']
                    xp_dict[pname] = half_xp
                result['xp_awarded'] = xp_dict
            
            socketio.emit('battle_result', result, room=room_code)
            
            # Trigger Rematch Question
            socketio.emit('battle_chat_message', {
                'sender': 'ByteBot',
                'message': "Do you want another round? (yes / no)",
                'type': 'system'
            }, room=room_code)
            
        except Exception as e:
            print(f"Judging error: {e}")
            socketio.emit('battle_error', {'message': 'AI Referee failed to judge. It\'s a draw!'}, room=room_code)

@socketio.on('battle_rematch_vote')
def on_battle_rematch_vote(data):
    room_code = data.get('room_code')
    vote = data.get('vote') # 'yes' or 'no'
    
    if not room_code or room_code not in battles:
        return
        
    room = battles[room_code]
    room['rematch_votes'][current_user.id] = vote
    
    player_name = room['players'][current_user.id]['name']
    
    # Notify about the vote
    emit('battle_chat_message', {'sender': 'ByteBot', 'message': f"{player_name} voted: {vote.upper()}", 'type': 'system'}, room=room_code)
    
    # If someone votes NO, end immediately (don't wait for both votes)
    if vote == 'no':
        emit('battle_chat_message', {
            'sender': 'ByteBot', 
            'message': f"{player_name} declined rematch. Battle concluded. Thanks for playing! 👋",
            'type': 'system'
        }, room=room_code)
        
        # Send event to close modal and return both players to entry screen
        emit('battle_rematch_declined', {}, room=room_code)
        return
    
    # If this person voted YES, notify the other player
    emit('battle_chat_message', {
        'sender': 'ByteBot', 
        'message': f"{player_name} wants a rematch! Waiting for opponent's response...",
        'type': 'system'
    }, room=room_code)
    
    # Check if everyone voted (both said yes)
    if len(room['rematch_votes']) == 2:
        votes = list(room['rematch_votes'].values())
        if all(v == 'yes' for v in votes):
            # Restart
            room['state'] = 'setup'
            room['submissions'] = {}
            room['problem'] = None
            room['config'] = {'difficulty': None, 'language': None}
            room['rematch_votes'] = {}
            
            emit('battle_restart', {}, room=room_code)
            emit('battle_chat_message', {
                'sender': 'ByteBot', 
                'message': "Rematch accepted! 🔥 Host, please choose settings again (Easy/Medium/Hard and Python/Java/C/JavaScript).",
                'type': 'system'
            }, room=room_code)

@socketio.on('battle_heartbeat')
def on_battle_heartbeat(data):
    """Handle heartbeat to keep connection alive and prevent disconnections"""
    if not current_user.is_authenticated:
        return
        
    room_code = data.get('room_code', '').strip().upper()
    if room_code not in battles:
        return
        
    room = battles[room_code]
    if current_user.id in room['players']:
        # Update SID to latest (handles reconnections/refreshes)
        room['players'][current_user.id]['sid'] = request.sid
        print(f"Heartbeat from {current_user.first_name} in {room_code}")



# Profile management can be extended later (kept simple for this semester project).

# ------------------------------
# FRIENDS & PROFILE LOGIC
# ------------------------------

@app.context_processor
def inject_user_context():
    if current_user.is_authenticated:
        # 1. Focus Buddies
        friends = []
        try:
            friendships = Friendship.query.filter(
                ((Friendship.user_id == current_user.id) | (Friendship.friend_id == current_user.id)) & 
                (Friendship.status == 'accepted')
            ).all()
            
            for f in friendships:
                fid = f.friend_id if f.user_id == current_user.id else f.user_id
                friend = User.query.get(fid)
                if friend:
                    # Check online status (within 5 mins)
                    is_online = (datetime.utcnow() - (friend.last_seen or datetime.min)) < timedelta(minutes=5)
                    friends.append({
                        'id': friend.id,
                        'name': f"{friend.first_name} {friend.last_name}",
                        'avatar': friend.get_avatar(64),
                        'is_online': is_online,
                        'is_public': friend.is_public_profile,
                        'rank': GamificationService.get_rank(friend.level) if friend.is_public_profile else None,
                        'stats': {'level': friend.level, 'xp': friend.total_xp} if friend.is_public_profile else None
                    })
        except Exception:
            pass # Fail gracefully if table doesn't exist yet
        
        # 2. Sidebar Stats (Rank, Level Progress)
        current_rank = GamificationService.get_rank(current_user.level)
        # XP per level is 500 (from GamificationService)
        xp_per_level = 500
        current_xp_in_level = current_user.total_xp % xp_per_level
        level_progress = int((current_xp_in_level / xp_per_level) * 100)
        xp_remaining = xp_per_level - current_xp_in_level
        
        return dict(
            focus_buddies=friends,
            rank_name=current_rank['name'],
            rank_icon=current_rank['icon'],
            rank_color=current_rank['color'],
            level_progress=level_progress,
            xp_remaining=xp_remaining
        )
    return dict(focus_buddies=[])

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        try:
            current_user.last_seen = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass # Fail silently to prevent request crash

@app.route('/settings/public-profile', methods=['POST'])
@login_required
def toggle_public_profile():
    data = request.get_json()
    current_user.is_public_profile = data.get('is_public', True)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/friends')
@login_required
def friends_page():
    # Helper to format user
    def format_user(u):
        return {
            'id': u.id,
            'name': f"{u.first_name} {u.last_name}",
            'email': u.email,
            'avatar': u.get_avatar(100),
            'level': u.level,
            'rank': GamificationService.get_rank(u.level),
            'is_public': u.is_public_profile
        }

    # 1. My Friends
    accepted = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) | (Friendship.friend_id == current_user.id)) & 
        (Friendship.status == 'accepted')
    ).all()
    my_friends = []
    for f in accepted:
        fid = f.friend_id if f.user_id == current_user.id else f.user_id
        friend = User.query.get(fid)
        if friend:
            my_friends.append(format_user(friend))

    # 2. Friend Requests (Received)
    requests = Friendship.query.filter_by(friend_id=current_user.id, status='pending').all()
    friend_requests = []
    for r in requests:
        sender = User.query.get(r.user_id)
        if sender:
            friend_requests.append({
                'request_id': r.id,
                **format_user(sender)
            })

    return render_template('friends.html', my_friends=my_friends, friend_requests=friend_requests)

@app.route('/api/users/search')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    
    # Search by name or email
    users = User.query.filter(
        (User.id != current_user.id) & 
        (
            (User.email.ilike(f"%{query}%")) | 
            (User.first_name.ilike(f"%{query}%")) | 
            (User.last_name.ilike(f"%{query}%"))
        )
    ).limit(10).all()
    
    results = []
    for u in users:
        # Check friendship status
        friendship = Friendship.query.filter(
            ((Friendship.user_id == current_user.id) & (Friendship.friend_id == u.id)) |
            ((Friendship.user_id == u.id) & (Friendship.friend_id == current_user.id))
        ).first()
        
        status = 'none'
        if friendship:
            status = friendship.status
            if status == 'pending' and friendship.friend_id == current_user.id:
                status = 'received' # Request received from this user
            elif status == 'pending' and friendship.user_id == current_user.id:
                status = 'sent' # Request sent to this user
        
        results.append({
            'id': u.id,
            'name': f"{u.first_name} {u.last_name}",
            'email': u.email,
            'avatar': u.get_avatar(64),
            'status': status
        })
        
    return jsonify(results)

@app.route('/friends/request/<int:user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot add self'}), 400
        
    target = User.query.get(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404
        
    existing = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == user_id)) |
        ((Friendship.user_id == user_id) & (Friendship.friend_id == current_user.id))
    ).first()
    
    if existing:
        return jsonify({'error': 'Friendship or request already exists'}), 400
        
    req = Friendship(user_id=current_user.id, friend_id=user_id, status='pending')
    db.session.add(req)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route('/friends/accept/<int:request_id>', methods=['POST'])
@login_required
def accept_friend_request(request_id):
    req = Friendship.query.get(request_id)
    if not req or req.friend_id != current_user.id:
        return jsonify({'error': 'Invalid request'}), 404
        
    req.status = 'accepted'
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/friends/reject/<int:request_id>', methods=['POST'])
@login_required
def reject_friend_request(request_id):
    req = Friendship.query.get(request_id)
    if not req or req.friend_id != current_user.id:
        return jsonify({'error': 'Invalid request'}), 404
        
    db.session.delete(req)
    db.session.commit()
    return jsonify({'status': 'success'})

# ------------------------------
# QUIZ SERVICE
# ------------------------------
class QuizService:
    @staticmethod
    def generate_weakness_quiz(user_id: int, **kwargs):
        import random
        
        # 1. Identify Active Syllabus (Context Awareness)
        # By default, use the most recent (Active) syllabus.
        # Ideally, passed via kwargs if we start quiz from archive, but for now default to Active.
        active_doc = SyllabusDocument.query.filter_by(user_id=user_id).order_by(SyllabusDocument.created_at.desc()).first()
        active_syllabus_id = active_doc.id if active_doc else None

        # 2. Get Topics from Active Syllabus Tasks
        # We only want to test on what is currently being studied.
        
        topics_list = []
        
        if active_syllabus_id:
            # Plan A: Get categories from Todos linked to this syllabus
            # We want unique categories from tasks in this syllabus
            
            # Efficient query for distinct categories in this syllabus
            # SQLAlchemy distinct can be tricky across DBs, let's fetch category names
            relevant_todos = (
                db.session.query(Todo.category)
                .filter(Todo.user_id == user_id)
                .filter(Todo.syllabus_id == active_syllabus_id)
                .filter(Todo.category != None)
                .distinct()
                .limit(20)
                .all()
            )
            
            syllabus_categories = [r[0] for r in relevant_todos if r[0]]
            
            # Now, from these categories, which ones are "Weak"?
            # We intersect with TopicProficiency (if any exists)
            
            if syllabus_categories:
                # Find proficiencies for these specific categories
                prof_records = (
                    TopicProficiency.query
                    .filter_by(user_id=user_id)
                    .filter(TopicProficiency.topic_name.in_(syllabus_categories))
                    .order_by(TopicProficiency.proficiency.asc()) # Lowest first
                    .limit(5)
                    .all()
                )
                
                # Add the weakest ones first
                topics_list.extend([p.topic_name for p in prof_records])
                
                # If we need more, just add random ones from the syllabus
                if len(topics_list) < 3:
                    remaining = list(set(syllabus_categories) - set(topics_list))
                    random.shuffle(remaining)
                    topics_list.extend(remaining[:3])
        
        # Fallback (If no active syllabus or no topics found in it)
        if not topics_list:
            # Fallback to old behavior: Global Weakness
            weak_topics = (
                TopicProficiency.query
                .filter_by(user_id=user_id)
                .filter(TopicProficiency.proficiency < 70)
                .order_by(TopicProficiency.proficiency.asc())
                .limit(5)
                .all()
            )
            topics_list = [t.topic_name for t in weak_topics]

        # Final Fill (if still empty)
        if len(topics_list) < 3:
             if active_syllabus_id:
                  # Force find ANY tasks from this syllabus
                  some_todos = Todo.query.filter_by(user_id=user_id, syllabus_id=active_syllabus_id).limit(20).all()
                  cats = list(set([t.category for t in some_todos if t.category]))
                  topics_list.extend(cats)
             else:
                  topics_list = ["General Study Skills", "Time Management", "Focus"]
        
        # Deduplicate and Limit
        topics_list = list(set(topics_list))[:5]
        if not topics_list:
             topics_list = ["General Knowledge"]

        num_questions = kwargs.get('num_questions', 5)
        difficulty = kwargs.get('difficulty', 'medium')
        
        # 2. Call AI
        # Minimal prompt to save tokens and ensure JSON
        topic_str = ", ".join(topics_list[:3]) # Limit to 3 topics for context
        prompt = (
            f"Create a {num_questions}-question multiple choice quiz testing knowledge on: {topic_str}. "
            f"Difficulty level: {difficulty}. "
            "Focus on identifying weaknesses. "
            "Output strictly valid JSON (no markdown formatting) in this specific format: "
            '{"questions": [{"question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0, "topic": "..."}]}'
        )

        messages = [{'role': 'user', 'content': prompt}]
        response_text = call_ai_api(messages)
        
        # 3. Parse JSON
        # Clean potential markdown codes
        clean_text = response_text.replace('```json', '').replace('```', '').strip()
        try:
            data = json.loads(clean_text)
            return data.get('questions', [])
        except json.JSONDecodeError:
            # Fallback or retry? For now, return error or mock
            print(f"Quiz JSON Parse Error: {clean_text}")
            return []

# ------------------------------
# MATCHMAKING SERVICE
# ------------------------------
class MatchmakingService:
    @staticmethod
    def find_matches(user):
        # 1. Get candidates (not self, not already friends)
        subq = db.session.query(Friendship.friend_id).filter(Friendship.user_id == user.id)
        subq2 = db.session.query(Friendship.user_id).filter(Friendship.friend_id == user.id)
        
        candidates = User.query.filter(
            User.id != user.id,
            ~User.id.in_(subq),
            ~User.id.in_(subq2),
            User.is_public_profile == True
        ).limit(50).all()
        
        matches = []
        user_proficiencies = {p.topic_name for p in TopicProficiency.query.filter_by(user_id=user.id).all()}
        
        for candidate in candidates:
            score = 0
            
            # Level Compatibility
            level_diff = abs(user.level - candidate.level)
            if level_diff <= 5:
                score += 20
            elif level_diff <= 10:
                score += 10
                
            # Topic Overlap
            cand_prof = {p.topic_name for p in TopicProficiency.query.filter_by(user_id=candidate.id).all()}
            overlap = user_proficiencies.intersection(cand_prof)
            score += len(overlap) * 10
            
            # Recency
            if candidate.last_seen: 
                 delta = datetime.utcnow() - candidate.last_seen
                 if delta < timedelta(days=1):
                    score += 30 
                 elif delta < timedelta(days=7):
                    score += 10
            
            # Random jitter to keep list fresh if scores are tie
            score += random.randint(0, 5)

            matches.append({
                'user': candidate,
                'score': score,
                'common_topics': list(overlap)[:3]
            })
            
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:5]

@app.route('/api/matches')
@login_required
def get_matches():
    raw_matches = MatchmakingService.find_matches(current_user)
    results = []
    for m in raw_matches:
        u = m['user']
        current_rank = GamificationService.get_rank(u.level)
        results.append({
            'id': u.id,
            'name': f"{u.first_name} {u.last_name}",
            'avatar': u.get_avatar(64),
            'level': u.level,
            'match_score': m['score'],
            'common_topics': m['common_topics'],
            'rank': current_rank
        })
    return jsonify(results)

@app.route('/quiz')
@login_required
def quiz_page():
    return render_template('quiz.html')

@app.route('/api/quiz/generate', methods=['POST'])
@login_required
def quiz_generate():
    data = request.json or {}
    num_questions = int(data.get('num_questions', 5))
    difficulty = data.get('difficulty', 'medium')
    
    questions = QuizService.generate_weakness_quiz(current_user.id, num_questions=num_questions, difficulty=difficulty)
    if not questions:
        # Fallback Mock if AI fails
        questions = [
            {
                "question": "Which technique helps most with procrastination?", 
                "options": ["Pomodoro Technique", "Doom Scrolling", "Multitasking", "Sleeping"], 
                "correct_index": 0, 
                "topic": "Study Skills"
            }
        ]
        # return jsonify({'status': 'error', 'message': 'AI failed to generate quiz.'}), 500
    
    return jsonify({'status': 'success', 'questions': questions})

@app.route('/api/quiz/submit', methods=['POST'])
@login_required
def quiz_submit():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
        
    answers = data.get('answers', [])
    # answers: [{topic: 'Math', correct: true}, ...]
    
    xp_earned = 0
    correct_count = 0
    
    import random
    
    for ans in answers:
        is_correct = ans.get('correct', False)
        topic_name = ans.get('topic')
        
        if is_correct:
            correct_count += 1
            xp_earned += 20 # 20 XP per correct answer
            
            # Boost proficiency
            if topic_name:
                prof = TopicProficiency.query.filter_by(user_id=current_user.id, topic_name=topic_name).first()
                if not prof:
                    prof = TopicProficiency(user_id=current_user.id, topic_name=topic_name, proficiency=20)
                    db.session.add(prof)
                else:
                    prof.proficiency = min(100, prof.proficiency + 5)
                    prof.updated_at = datetime.utcnow()
        else:
             # Lower proficiency slightly?
             if topic_name:
                prof = TopicProficiency.query.filter_by(user_id=current_user.id, topic_name=topic_name).first()
                if prof and prof.proficiency > 5:
                    prof.proficiency = max(0, prof.proficiency - 2)
                    prof.updated_at = datetime.utcnow()

    # Bonus for perfect score
    if correct_count == len(answers) and correct_count > 0:
        xp_earned += 50
        GamificationService.award_badge(current_user, 'Quiz Master') # Need to ensure badge exists or create dynamically handling it

    # Save XP
    if xp_earned > 0:
        GamificationService.add_xp(current_user.id, 'quiz', xp_earned)
        
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'score': correct_count,
        'xp_earned': xp_earned
    })


# ------------------------------
# WHITEBOARD SOCKET EVENTS
# ------------------------------
@socketio.on('wb_draw')
def handle_wb_draw(data):
    room = data.get('room')
    if room:
        # Broadcast to all in room except sender
        emit('wb_draw', data, room=str(room), broadcast=True, skip_sid=request.sid)

@socketio.on('wb_clear')
def handle_wb_clear(data):
    room = data.get('room')
    if room:
        # Broadcast clear command to all users in room
        emit('wb_clear', data, room=str(room), broadcast=True, include_self=True)

@socketio.on('join')
def on_join(data):
    username = data.get('username')
    room = data.get('room')
    if room:
        join_room(room)

# -----------------
# EVENT API
# -----------------

@app.route('/api/events', methods=['GET', 'POST'])
@login_required
def handle_events():
    if request.method == 'POST':
        data = request.json
        new_event = Event(
            user_id=current_user.id,
            title=data.get('title'),
            description=data.get('description', ''),
            date=data.get('date'),
            time=data.get('time', '')
        )
        db.session.add(new_event)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Event created successfully!', 'id': new_event.id})

    date_filter = request.args.get('date')
    query = Event.query.filter_by(user_id=current_user.id)
    if date_filter:
        query = query.filter_by(date=date_filter)
    events = query.order_by(Event.date.asc(), Event.time.asc()).all()
    
    return jsonify({
        'status': 'success',
        'events': [{
            'id': e.id,
            'title': e.title,
            'description': e.description,
            'date': e.date,
            'time': e.time,
            'is_notified': e.is_notified
        } for e in events]
    })

@app.route('/api/events/<int:event_id>', methods=['PUT', 'DELETE'])
@login_required
def single_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    if request.method == 'DELETE':
        db.session.delete(event)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Event deleted'})
        
    if request.method == 'PUT':
        data = request.json
        event.title = data.get('title', event.title)
        event.description = data.get('description', event.description)
        event.date = data.get('date', event.date)
        event.time = data.get('time', event.time)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Event updated'})

@app.route('/api/events/check-warnings', methods=['GET'])
@login_required
def check_event_warnings():
    # Get current IST time
    now_ist = datetime.now(IST)
    today_str = now_ist.strftime('%Y-%m-%d')
    current_time_str = now_ist.strftime('%H:%M')
    
    # Find active events for today that have arrived but not notified
    # We check if event.time <= current_time_str
    active_event = Event.query.filter_by(user_id=current_user.id, date=today_str, is_notified=False)\
        .filter(Event.time <= current_time_str)\
        .order_by(Event.time.desc()).first()
    
    return jsonify({
        'status': 'success',
        'has_warning': bool(active_event),
        'event': {
            'id': active_event.id,
            'title': active_event.title,
            'description': active_event.description,
            'time': active_event.time
        } if active_event else None
    })

@app.route('/api/important', methods=['GET'])
@login_required
def get_important():
    # Get current IST time
    now_ist = datetime.now(IST)
    today_str = now_ist.strftime('%Y-%m-%d')
    time_str = now_ist.strftime('%H:%M')

    # Next event today or in the future (strictly future, not current minute)
    important_event = Event.query.filter(
        Event.user_id == current_user.id,
        Event.date >= today_str
    ).filter(
        db.or_(
            Event.date > today_str,
            db.and_(Event.date == today_str, db.or_(Event.time > time_str, Event.time == None, Event.time == ''))
        )
    ).order_by(Event.date.asc(), Event.time.asc()).first()

    # High priority uncompleted task
    important_todo = Todo.query.filter_by(
        user_id=current_user.id,
        completed=False,
        priority='high'
    ).order_by(Todo.id.desc()).first()

    important_todo_label = "High Priority Task"
    
    if not important_todo:
        important_todo = Todo.query.filter(
            Todo.user_id == current_user.id,
            Todo.completed == False,
            Todo.due_date != None,
            Todo.due_date >= today_str
        ).order_by(Todo.due_date.asc()).first()
        
        if important_todo:
            important_todo_label = "Upcoming Task"

    res = {
        'event': {
            'title': important_event.title,
            'date': important_event.date,
            'time': important_event.time
        } if important_event else None,
        'todo': {
            'title': important_todo.title,
            'due_date': important_todo.due_date if important_todo.due_date else 'Soon',
            'label': important_todo_label,
            'priority': important_todo.priority
        } if important_todo else None
    }
    return jsonify(res)

@app.route('/api/active-tasks', methods=['GET'])
@login_required
def get_active_tasks():
    """Fetch the latest uncompleted tasks ordered by due_time, then priority."""
    # Get tasks ordered by due_date and due_time (if present)
    upcoming_todos = (
        Todo.query
        .filter_by(user_id=current_user.id, completed=False)
        .order_by(
            Todo.due_date.asc().nullslast(),
            Todo.due_time.asc().nullslast(),
            Todo.id.desc()
        )
        .limit(5)
        .all()
    )
    
    tasks = [{
        'id': t.id,
        'title': t.title,
        'priority': t.priority,
        'completed': t.completed,
        'due_date': t.due_date,
        'due_time': t.due_time
    } for t in upcoming_todos]
    
    return jsonify({'tasks': tasks, 'count': len(tasks)})

@app.route('/api/events/<int:event_id>/dismiss', methods=['POST'])
@login_required
def dismiss_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    event.is_notified = True
    db.session.commit()
    return jsonify({'status': 'success'})

def init_db_schema():
    from sqlalchemy import text, inspect
    
    with app.app_context():
        db.create_all()
        
        # Auto-migration for schema updates
        try:
            inspector = inspect(db.engine)
            with db.engine.connect() as conn:
                # 1. Check for file_path in group_chat_message
                if 'group_chat_message' in inspector.get_table_names():
                    columns = [c['name'] for c in inspector.get_columns('group_chat_message')]
                    if 'file_path' not in columns:
                        print("Running migration: Adding file_path to group_chat_message table...")
                        conn.execute(text("ALTER TABLE group_chat_message ADD COLUMN file_path VARCHAR(255)"))
                
                # 2. Check for columns in user table
                if 'user' in inspector.get_table_names():
                    columns = [c['name'] for c in inspector.get_columns('user')]
                    
                    # New Features (Friends/Public Profile)
                    if 'is_public_profile' not in columns:
                        print("Running migration: Adding is_public_profile to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN is_public_profile BOOLEAN DEFAULT TRUE'))
                    if 'last_seen' not in columns:
                        print("Running migration: Adding last_seen to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN last_seen TIMESTAMP'))
                    
                    # Existing checks
                    if 'cover_image' not in columns:
                        print("Running migration: Adding cover_image to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN cover_image VARCHAR(255)'))
                    if 'google_id' not in columns:
                        print("Running migration: Adding google_id to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN google_id VARCHAR(100)'))
                    if 'profile_image' not in columns:
                        print("Running migration: Adding profile_image to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN profile_image VARCHAR(255)'))
                    
                    # Gamification Migrations
                    if 'total_xp' not in columns:
                        print("Running migration: Adding total_xp to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN total_xp INTEGER DEFAULT 0'))
                    if 'level' not in columns:
                        print("Running migration: Adding level to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN level INTEGER DEFAULT 1'))
                    if 'current_streak' not in columns:
                        print("Running migration: Adding current_streak to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN current_streak INTEGER DEFAULT 0'))
                    if 'longest_streak' not in columns:
                        print("Running migration: Adding longest_streak to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN longest_streak INTEGER DEFAULT 0'))
                    if 'last_activity_date' not in columns:
                        print("Running migration: Adding last_activity_date to user table...")
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN last_activity_date DATE'))
                    
                # 3. Check for Todo table updates
                if 'todo' in inspector.get_table_names():
                    columns = [c['name'] for c in inspector.get_columns('todo')]
                    if 'completed_at' not in columns:
                         print("Running migration: Adding completed_at to todo table...")
                         conn.execute(text("ALTER TABLE todo ADD COLUMN completed_at TIMESTAMP"))
                    if 'is_group' not in columns:
                         print("Running migration: Adding is_group to todo table...")
                         conn.execute(text("ALTER TABLE todo ADD COLUMN is_group BOOLEAN DEFAULT FALSE"))
                    if 'category' not in columns:
                         print("Running migration: Adding category to todo table...")
                         conn.execute(text("ALTER TABLE todo ADD COLUMN category VARCHAR(50)"))
                    if 'due_time' not in columns:
                         print("Running migration: Adding due_time to todo table...")
                         conn.execute(text("ALTER TABLE todo ADD COLUMN due_time VARCHAR(20)"))
                    if 'is_notified' not in columns:
                         print("Running migration: Adding is_notified to todo table...")
                         conn.execute(text("ALTER TABLE todo ADD COLUMN is_notified BOOLEAN DEFAULT FALSE"))

                # 4. Check for SyllabusDocument updates
                if 'syllabus_document' in inspector.get_table_names():
                    columns = [c['name'] for c in inspector.get_columns('syllabus_document')]
                    if 'extracted_text' not in columns:
                        print("Running migration: Adding extracted_text to syllabus_document table...")
                        conn.execute(text("ALTER TABLE syllabus_document ADD COLUMN extracted_text TEXT"))
                
                # 4. Create Habit tables if missing (Standard approach)
                # Since we use db.create_all() at startup, this is mainly for verification or alter
                if 'habit' not in inspector.get_table_names():
                    print("Creating habit table...")
                    print("Creating habit table...")
                    db.create_all() 
                        
                conn.commit()
            print("Migration checks completed.")
        except Exception as e:
            print(f"Migration check failed (safe to ignore if new DB): {e}")

def run_xp_update():
    """Updates specific user XP and recalculates levels on startup."""
    try:
        with app.app_context():
            # 1. Update Daksh's XP (Case-insensitive)
            target_name = 'daksh'
            users_found = User.query.filter(User.first_name.ilike(target_name)).all()
            
            if users_found:
                print(f"--- Running XP Update for '{target_name}' ---")
                for user in users_found:
                    user.total_xp += 100000
                    print(f"  > Incremented {user.first_name}'s XP by 100,000. New XP: {user.total_xp}")

            # 2. Recalculate Levels for ALL users
            print("--- Recalculating Levels/Ranks for All Users ---")
            all_users = User.query.all()
            updated_count = 0
            for u in all_users:
                correct_level = GamificationService.calculate_level(u.total_xp)
                if u.level != correct_level:
                    u.level = correct_level
                    updated_count += 1
            
            if updated_count > 0:
                print(f"  > Adjusted levels for {updated_count} users.")
                
            db.session.commit()
            print("--- User Status Synchronization Complete ---")
    except Exception as e:
        print(f"XP/Rank Update failed: {e}")

# Global scheduler flag to prevent duplicates
SCHEDULER_STARTED = False

def check_task_reminders():
    """
    Background job to check for due tasks and send emails.
    Check every 60 seconds.
    """
    while True:
        try:
            with app.app_context():
                now_utc = datetime.utcnow()
                # IST = UTC + 5:30
                now_ist = now_utc + timedelta(hours=5, minutes=30)
                
                # Format for comparison
                current_date_str = now_ist.strftime('%Y-%m-%d')
                current_time_str = now_ist.strftime('%H:%M')
                
                # Check for tasks due TODAY that haven't been notified
                # Logic: Due Date is today AND (Time is approaching OR Time is null)
                # Specific logic: Notify if Due Time is within next 1 hour
                
                # Query all un-notified tasks due today
                upcoming_tasks = Todo.query.filter(
                    Todo.due_date == current_date_str,
                    Todo.completed == False,
                    Todo.is_notified == False
                ).all()
                
                for task in upcoming_tasks:
                    should_notify = False
                    
                    if not task.due_time:
                        # All-day task: Notify at 9 AM or immediately if created later
                        # For simplicity, we can notify immediately if it's today
                        should_notify = True 
                    else:
                        # Time-specific task
                        # Convert due_time (HH:MM) to numeric or simplified compare
                        # Simple compare: Notify if Current Time < Due Time <= Current Time + 1 Hour
                         try:
                            # Simple string comparison works for HH:MM 24h format
                            # Notify if we are past the time or close to it?
                            # Users asked for: "due date is now due" -> alert
                            
                            # Let's alert if current time is >= due time (it's due!)
                            # OR slightly before? Lets say 15 mins before or ON time.
                            # For robustness: Alert if Current Time >= Due Time
                            
                            if current_time_str >= task.due_time:
                                should_notify = True
                                
                         except Exception:
                             pass
                             
                    if should_notify:
                        # Fetch user manually if needed, or use relationship
                        user = User.query.get(task.user_id)
                        if user and user.email:
                            print(f"Sending reminder for task {task.id} to {user.email}")
                            sent = send_task_reminder_email(
                                user.email, 
                                user.first_name, 
                                task.title, 
                                task.due_date, 
                                task.due_time
                            )
                            if sent:
                                task.is_notified = True
                                db.session.commit()
                                
        except Exception as e:
            print(f"Scheduler Error: {e}")
            
        # Sleep for 60 seconds
        eventlet.sleep(60)

# IMPORTANT: Order matters. Define logic, THEN run schema check and updates.
init_db_schema()
run_xp_update()

@app.route('/fix-db-schema')
def fix_db_schema():
    """Manual trigger to fix DB schema in production."""
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # Postgres specific: Try adding the column directly
            try:
                conn.execute(text("ALTER TABLE todo ADD COLUMN IF NOT EXISTS syllabus_id INTEGER REFERENCES syllabus_document(id)"))
                conn.commit()
                return "Schema updated safely (Added syllabus_id)."
            except Exception as e:
                return f"Error executing ALTER: {str(e)}"
    except Exception as e:
        return f"Database connection error: {str(e)}"

if __name__ == '__main__':
    # Start Background Scheduler
    if not SCHEDULER_STARTED:
        eventlet.spawn(check_task_reminders)
        SCHEDULER_STARTED = True

    # Use socketio.run instead of app.run
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
