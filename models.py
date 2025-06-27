from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json

class SyncLog(db.Model):
    """Log of synchronization operations"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    operation_type = db.Column(db.String(50), nullable=False)  # 'extract', 'sync', 'test'
    source_system = db.Column(db.String(20))  # 'opdv', 'omie'
    status = db.Column(db.String(20), nullable=False)  # 'success', 'error', 'warning'
    message = db.Column(db.Text)
    records_affected = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<SyncLog {self.operation_type} - {self.status}>'

class ConnectionConfig(db.Model):
    """Store connection configurations"""
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(20), nullable=False, unique=True)  # 'opdv', 'omie'
    config_data = db.Column(db.Text)  # JSON string of configuration
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ConnectionConfig {self.service_name}>'


class PreviewData(db.Model):
    """Store extracted preview data"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), nullable=False)
    data_type = db.Column(db.String(20), nullable=False)  # 'orders' or 'customers'
    data_json = db.Column(db.Text, nullable=False)  # JSON string of data
    total_count = db.Column(db.Integer, default=0)
    extracted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_data(self):
        """Get data as Python object"""
        return json.loads(self.data_json)
    
    def set_data(self, data):
        """Set data from Python object"""
        self.data_json = json.dumps(data)
    
    def __repr__(self):
        return f'<PreviewData {self.data_type}: {self.total_count}>'


class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
