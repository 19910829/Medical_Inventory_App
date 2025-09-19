import bcrypt
import streamlit as st
from database import get_db_connection

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user_table():
    """Create users table if it doesn't exist"""
    conn = get_db_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'employee')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    
    # Create default admin user if no users exist
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    
    if user_count == 0:
        admin_password = hash_password("admin123")
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            ("admin", admin_password, "admin")
        )
        
        employee_password = hash_password("employee123")
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            ("employee", employee_password, "employee")
        )
    
    conn.commit()
    cur.close()
    conn.close()

def authenticate_user(username, password):
    """Authenticate user credentials"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    
    cur.execute(
        "SELECT username, password_hash, role FROM users WHERE username = %s AND is_active = TRUE",
        (username,)
    )
    
    user = cur.fetchone()
    
    if user and verify_password(password, user[1]):
        # Update last login
        cur.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = %s",
            (username,)
        )
        conn.commit()
        
        cur.close()
        conn.close()
        
        return {
            'username': user[0],
            'role': user[2]
        }
    
    cur.close()
    conn.close()
    return None

def get_user_info(username):
    """Get user information"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    
    cur.execute(
        "SELECT username, role, created_at, last_login FROM users WHERE username = %s",
        (username,)
    )
    
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return {
            'username': user[0],
            'role': user[1],
            'created_at': user[2],
            'last_login': user[3]
        }
    
    return None
