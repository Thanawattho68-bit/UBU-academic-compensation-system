"""
utils/helpers.py
ฟังก์ชันช่วยเหลือต่างๆ ที่ใช้ร่วมกันทั่วทั้งแอปพลิเคชัน
ผู้รับผิดชอบ: ทีมพัฒนา
"""

import json
import os
import tempfile
from datetime import datetime
from database import query_db, execute_db


# ──────────────────────────────────────────────
# File I/O Helpers (JSON)
# ──────────────────────────────────────────────

def load_data(filename):
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=4)
        return []
    if os.path.getsize(filename) == 0: return []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []


def load_config(filename, default=None):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return default


def save_data(filename, data):
    # Create a temporary file in the same directory as the target
    dir_name = os.path.dirname(os.path.abspath(filename))
    fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # Rename the temp file to the target filename (atomic on most OS)
        os.replace(temp_path, filename)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


# ──────────────────────────────────────────────
# Date Helpers
# ──────────────────────────────────────────────

def to_thai_year(date_obj):
    return date_obj.year + 543


def format_thai_date(date_obj, include_time=False):
    if not date_obj: return ""
    y = date_obj.year + 543
    if include_time:
        return date_obj.strftime(f"%d/%m/{y} %H:%M")
    return date_obj.strftime(f"%d/%m/{y}")


def parse_thai_date(date_str):
    if not date_str: return None
    date_str = date_str.strip()
    # Handle YYYY-MM-DD (standard HTML5 date input)
    try:
        if '-' in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except: pass
    
    # Handle DD/MM/YYYY or D/M/Y (Thai BE)
    for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            
            # If it's just d/m, assume current year
            if fmt == "%d/%m":
                dt = dt.replace(year=datetime.now().year)
            
            if dt.year > 2400:
                dt = dt.replace(year=dt.year - 543)
            elif fmt == "%d/%m/%y":
                # Always treat 2-digit year as BE (25xx)
                # AD = (2500 + y) - 543 = 1957 + y
                # Since strptime %y gives 2000 + y or 1900 + y:
                if dt.year >= 2000:
                    dt = dt.replace(year=dt.year - 43) # (2000+y) - 43 = 1957+y
                else: 
                    dt = dt.replace(year=dt.year + 57) # (1900+y) + 57 = 1957+y
            
            return dt
        except: continue
    return None


# ──────────────────────────────────────────────
# Fiscal Year / Timeline Helpers
# ──────────────────────────────────────────────

def get_current_fiscal_year():
    today = datetime.now()
    # Fiscal Year Rule: Starts Oct 1 of Year X-1 ends Sep 30 of Year X -> FY X
    if today.month >= 10:
        return today.year + 543 + 1
    return today.year + 543


def is_within_timeline():
    current_fy = get_current_fiscal_year()
    # Try current year, if not found, get the latest one available
    config = query_db('SELECT * FROM FiscalYearConfig WHERE fiscal_year = ?', (str(current_fy),), one=True)
    if not config:
        config = query_db('SELECT * FROM FiscalYearConfig ORDER BY fiscal_year DESC LIMIT 1', one=True)
        
    if not config:
        return True # Default open if absolutely no config exists

    now = datetime.now()
    
    # Simple check against global start/end dates in BE format (DD/MM/YYYY)
    dt_main_start = parse_thai_date(config['start_date'])
    dt_main_end = parse_thai_date(config['end_date'])
    
    if dt_main_start and dt_main_end:
        # Set time to start of day and end of day
        dt_main_start = dt_main_start.replace(hour=0, minute=0, second=0)
        dt_main_end = dt_main_end.replace(hour=23, minute=59, second=59)
        return dt_main_start <= now <= dt_main_end
    
    return True


def get_remaining_days(start_date_str, limit_days=7):
    if not start_date_str: return limit_days
    start_dt = parse_thai_date(start_date_str)
    if not start_dt: return limit_days
    delta = datetime.now() - start_dt
    return limit_days - delta.days


# ──────────────────────────────────────────────
# File Upload Helpers
# ──────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'zip', 'rar'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ──────────────────────────────────────────────
# Notification Helper
# ──────────────────────────────────────────────

def create_notification(message, recipient_role=None, recipient_username=None, req_id=None):
    notif_id = f"NOTIF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
    timestamp = format_thai_date(datetime.now(), True)
    execute_db('''
        INSERT INTO Notification (id, message, recipient_role, recipient_username, req_id, is_read, timestamp)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    ''', (notif_id, message, recipient_role, recipient_username, req_id, timestamp))


# ──────────────────────────────────────────────
# Compensation Calculation
# ──────────────────────────────────────────────

def calculate_compensation(works_list, position_str, fiscal_year_req):
    # Load config
    all_criteria = load_config('criteria.json', [])
    if isinstance(all_criteria, dict): all_criteria = []
    
    # Find matching criteria or use default/latest
    criteria = next((c for c in all_criteria if str(c.get('fiscal_year')) == str(fiscal_year_req)), None)
    if not criteria and all_criteria:
        criteria = all_criteria[0]
        
    qs = criteria.get('quality_scores', {}) if criteria else {}
    rw = criteria.get('role_weights', {}) if criteria else {}
    pr = criteria.get('payment_rules', {}) if criteria else {}

    score_sum = 0
    
    # Normalize Position
    pos = position_str.strip() if position_str else ""
    is_asst = 'ผู้ช่วยศาสตราจารย์' in pos
    is_assoc = 'รองศาสตราจารย์' in pos
    is_prof = 'ศาสตราจารย์' in pos and not is_asst and not is_assoc
    
    for w in works_list:
        if w.get('status') in ['ไม่อนุมัติ', 'ผลงานซ้ำซ้อน']:
            w['score_calc'] = 0
            w['payment_calc'] = 0
            w['score_breakdown'] = "ไม่อนุมัติการพิจารณา / ผลงานซ้ำซ้อน"
            continue

        w_type = w.get('type')
        details = w.get('details', {})
        s = 0.0
        weight = 0.0
        
        # 1. Determine Base Score (S)
        if w_type == 'research':
            rs = qs.get('research', {})
            db = details.get('database')
            if db == 'scopus_q1_q2': s = rs.get('tier1', 1.25)
            elif db == 'scopus_other': s = rs.get('non_q', 1.00)
            elif db == 'national': s = rs.get('national', 0.75)
        
        elif w_type in ['social', 'industry', 'teaching', 'policy', 'innovation'] or (w_type.startswith('custom_') and details.get('level')):
            # Use merged ABC scores
            type_scores = qs.get('merged_abc', {'a_plus': 1.25, 'a': 1.0, 'b': 0.75})
            lvl = details.get('level')
            if lvl == 'level_a_plus': s = type_scores.get('a_plus', 1.25)
            elif lvl == 'level_a': s = type_scores.get('a', 1.00)
            elif lvl == 'level_b': s = type_scores.get('b', 0.75)
            else: s = type_scores.get('a', 1.00)

        elif w_type == 'textbook':
            ts = qs.get('textbook', {'publisher': 1.25, 'general': 1.0})
            pt = details.get('publish_type')
            if pt == 'inter': s = ts.get('publisher', 1.25)
            elif pt == 'local': s = ts.get('general', 1.00)
            else: s = ts.get('publisher', 1.25)
            
        elif w_type == 'creative':
            cs = qs.get('creative', {'international': 1.25, 'cooperation': 1.00, 'national': 0.75})
            pt = details.get('publish_type', '')
            if 'inter' in pt: s = cs.get('international', 1.25)
            elif 'coop' in pt: s = cs.get('cooperation', 1.00)
            elif 'national' in pt: s = cs.get('national', 0.75)
            else: s = cs.get('international', 1.25)
        
        # 2. Determine Weight (W)
        role = details.get('contribution')
        if role in ['first', 'corresponding', 'main']:
            weight = rw.get('main', 1.0)
        elif role in ['intellectual', 'co']:
            weight = rw.get('co', 0.5)
        else:
            weight = 0.0
            
        # Net Score
        net = s * weight
        w['base_score'] = s
        w['weight'] = weight
        w['score_calc'] = net
        
        # Breakdown Text
        base_info = ""
        if w_type == 'research':
            db = details.get('database', '-')
            if db == 'scopus_q1_q2': base_info = "Scopus Q1/Q2"
            elif db == 'scopus_other': base_info = "Scopus Other"
            elif db == 'national': base_info = "TCI/National"
        elif w_type in ['social', 'industry', 'teaching', 'policy', 'innovation']:
            lvl = details.get('level', '-')
            base_info = f"{w_type.capitalize()} ({lvl.replace('level_', '').upper()})"
        else:
            base_info = w_type.capitalize()
            
        w['score_breakdown'] = f"ฐาน {s} ({base_info}) x น้ำหนัก {weight}"
        w['payment_calc'] = 0 
        score_sum += net

    # 3. Calculate compensation based on Tiers
    comp = 0
    pos_key = 'asst_prof' if is_asst else ('assoc_prof' if is_assoc else ('prof' if is_prof else ''))
    
    if pos_key:
        tiers = pr.get(pos_key, [])
        if isinstance(tiers, dict): # Handle legacy single tier
             if score_sum >= tiers.get('min_score', 0): comp = tiers.get('amount', 0)
        elif isinstance(tiers, list):
            # Only consider up to 2 tiers as requested (though logic finds best fit anyway)
            applicable_tiers = [t for t in tiers if score_sum >= float(t.get('min_score', 0))]
            if applicable_tiers:
                applicable_tiers.sort(key=lambda x: float(x.get('min_score', 0)), reverse=True)
                comp = float(applicable_tiers[0].get('amount', 0))

    return score_sum, comp
