import sqlite3
import os

DATABASE_PATH = os.path.join('instance', 'database.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
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
            name TEXT,
            role TEXT,
            title_name TEXT,
            academic_position TEXT,
            department TEXT,
            faculty TEXT,
            position_date TEXT,
            position_number TEXT
        )
    ''')
    
    # RequestRecord table (Simplified with works_json)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS RequestRecord (
            id TEXT PRIMARY KEY,
            applicant_username TEXT NOT NULL,
            applicant_name TEXT,
            fiscal_year TEXT,
            status TEXT,
            date_submitted TEXT,
            total_score REAL DEFAULT 0.0,
            approved_amount REAL DEFAULT 0.0,
            comment TEXT,
            timeline_status TEXT,
            batch_id TEXT,
            applicant_info_json TEXT,
            works_json TEXT
        )
    ''')
    
    # Notification table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Notification (
            id TEXT PRIMARY KEY,
            message TEXT NOT NULL,
            recipient_role TEXT,
            recipient_username TEXT,
            req_id TEXT,
            is_read INTEGER DEFAULT 0,
            timestamp TEXT
        )
    ''')

    # FiscalYearConfig table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS FiscalYearConfig (
            fiscal_year TEXT PRIMARY KEY,
            start_date TEXT, -- Format: DD/MM/YYYY (BE)
            end_date TEXT    -- Format: DD/MM/YYYY (BE)
        )
    ''')

    # TimelineRound table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS TimelineRound (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fiscal_year TEXT,
            round_name TEXT,
            round_type TEXT, -- 'submission' หรือ 'consideration'
            start_date TEXT, -- Format: DD/MM/YYYY (BE)
            end_date TEXT,   -- Format: DD/MM/YYYY (BE)
            FOREIGN KEY (fiscal_year) REFERENCES FiscalYearConfig (fiscal_year) ON DELETE CASCADE
        )
    ''')

    # Criteria table (JSON storage)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Criteria (
            fiscal_year TEXT PRIMARY KEY,
            quality_scores TEXT,
            role_weights TEXT,
            payment_rules TEXT
        )
    ''')

    # WorkType table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS WorkType (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            is_custom INTEGER DEFAULT 0
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
