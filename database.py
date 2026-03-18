import sqlite3
import os

DATABASE_PATH = os.path.join('instance', 'database.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute('PRAGMA foreign_keys = ON;')  # Enable Foreign Key support
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Account table (Renamed from User)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            title_name TEXT,
            academic_position TEXT,
            department TEXT NOT NULL,
            faculty TEXT NOT NULL,
            position_date TEXT,
            position_number TEXT
        )
    ''')
    
    # RequestRecord table (Upgraded with Audit Trail)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS RequestRecord (
            id TEXT PRIMARY KEY,
            applicant_username TEXT NOT NULL,
            applicant_name TEXT NOT NULL,
            fiscal_year TEXT NOT NULL,
            status TEXT NOT NULL,
            date_submitted TEXT NOT NULL,
            total_score REAL DEFAULT 0.0,
            approved_amount REAL DEFAULT 0.0,
            applicant_info_json TEXT,
            works_json TEXT,
            works_draft_json TEXT,
            draft_owner TEXT,
            admin_viewer TEXT,
            research_viewer TEXT,
            committee_approver TEXT,
            final_approver TEXT,
            history_json TEXT,
            FOREIGN KEY (applicant_username) REFERENCES Account (username),
            FOREIGN KEY (fiscal_year) REFERENCES TimelineConfig (fiscal_year)
        )
    ''')
    
    # Notification table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Notification (
            id TEXT PRIMARY KEY,
            message TEXT NOT NULL,
            recipient_role TEXT,
            recipient_username TEXT NOT NULL,
            req_id TEXT,
            is_read INTEGER DEFAULT 0,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (recipient_username) REFERENCES Account (username),
            FOREIGN KEY (req_id) REFERENCES RequestRecord (id) ON DELETE CASCADE
        )
    ''')

    # TimelineConfig table (Merged & Flexible)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS TimelineConfig (
            fiscal_year TEXT PRIMARY KEY,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            rounds_json TEXT
        )
    ''')

    # Criteria table (JSON storage)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Criteria (
            fiscal_year TEXT PRIMARY KEY,
            quality_scores TEXT,
            role_weights TEXT,
            payment_rules TEXT,
            FOREIGN KEY (fiscal_year) REFERENCES TimelineConfig (fiscal_year)
        )
    ''')

    # WorkType table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS WorkType (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# Helper functions for common operations
def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db_connection()
    cur = conn.execute(query, args)
    conn.commit()
    lastrowid = cur.lastrowid
    conn.close()
    return lastrowid
