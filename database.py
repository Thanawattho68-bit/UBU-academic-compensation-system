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
    
    # RequestRecord table (Upgraded with Audit Trail)
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
            comments_json TEXT,
            timeline_status TEXT,
            batch_id TEXT,
            applicant_info_json TEXT,
            works_json TEXT,
            admin_viewer TEXT,
            research_viewer TEXT,
            committee_approver TEXT,
            final_approver TEXT,
            decision_reason TEXT,
            history_json TEXT
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

    # TimelineConfig table (Merged & Flexible)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS TimelineConfig (
            fiscal_year TEXT PRIMARY KEY,
            start_date TEXT,
            end_date TEXT,
            rounds_json TEXT
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
            is_custom INTEGER DEFAULT 0,
            calculation_mode TEXT DEFAULT 'self_assessment'
        )
    ''')
    
    # Ensure calculation_mode column exists (migration for existing DB)
    cursor.execute("PRAGMA table_info(WorkType)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'calculation_mode' not in columns:
        print("[DB MIGRATION] Adding 'calculation_mode' column to WorkType table...")
        cursor.execute("ALTER TABLE WorkType ADD COLUMN calculation_mode TEXT DEFAULT 'self_assessment'")
    else:
        print("[DB MIGRATION] 'calculation_mode' column already exists.")
    
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
