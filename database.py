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
    
    # User table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS User (
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
    
    # RequestRecord table
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
            applicant_info_json TEXT
        )
    ''')
    
    # WorkDetail table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS WorkDetail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            work_type TEXT,
            status TEXT,
            score_calc REAL,
            payment_calc REAL,
            details_json TEXT,
            FOREIGN KEY (request_id) REFERENCES RequestRecord (id) ON DELETE CASCADE
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

    # Criteria table (Approach 2: JSON storage with fiscal_year PK)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Criteria (
            fiscal_year TEXT PRIMARY KEY,
            quality_scores_json TEXT,
            role_weights_json TEXT,
            payment_rules_json TEXT
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
