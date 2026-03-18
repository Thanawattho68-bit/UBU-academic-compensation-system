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
# Request Deserialization Helper
# ──────────────────────────────────────────────

def deserialize_request(row):
    """แปลง row จาก DB (sqlite3.Row) เป็น dict พร้อม works, applicant_info, etc."""
    req = dict(row)
    req['works'] = json.loads(req['works_json']) if req.get('works_json') else []
    req['applicant_info'] = json.loads(req['applicant_info_json']) if req.get('applicant_info_json') else {}
    req['audit_trail'] = json.loads(req['history_json']) if req.get('history_json') else []
    req['applicant'] = req['applicant_username']  # Compatibility alias
    req['date'] = req['date_submitted']            # Compatibility alias
    req['score'] = req['total_score']              # Compatibility alias
    return req


def parse_academic_position(raw):
    """แปลง academic_position จาก DB (str/JSON) → list[str]"""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError):
        return [raw]


# ──────────────────────────────────────────────
# Date Helpers
# ──────────────────────────────────────────────

def to_thai_year(date_obj):
    return date_obj.year + 543


def format_thai_date(date_obj, include_time=False):
    """
    จัดรูปแบบวันที่/เวลา เป็นภาษาไทย (ปี พ.ศ.)
    รองรับทั้ง datetime object หรือ string (ISO format หรือ Thai format)
    """
    if not date_obj: return ""
    
    # ถ้าเป็น string ให้ลองแปลงเป็น datetime ก่อน
    if isinstance(date_obj, str):
        parsed = parse_thai_date(date_obj)
        if not parsed: return date_obj # คืนค่าเดิมถ้าแปลงไม่ได้
        date_obj = parsed

    y = date_obj.year + 543
    if include_time:
        return date_obj.strftime(f"%d/%m/{y} %H:%M")
    return date_obj.strftime(f"%d/%m/{y}")


def format_iso_date(date_obj, include_time=True):
    """
    จัดรูปแบบวันที่/เวลา เป็นมาตรฐาน ISO 8601 (สำหรับคลังฐานข้อมูล)
    """
    if not date_obj: return None
    if isinstance(date_obj, str):
        parsed = parse_thai_date(date_obj)
        if not parsed: return date_obj
        date_obj = parsed
    
    fmt = "%Y-%m-%d %H:%M:%S" if include_time else "%Y-%m-%d"
    return date_obj.strftime(fmt)


def parse_thai_date(date_str):
    if not date_str: return None
    date_str = date_str.strip()
    
    # Mapping for Thai months
    thai_months = {
        'ม.ค.': 1, 'ก.พ.': 2, 'มี.ค.': 3, 'เม.ย.': 4, 'พ.ค.': 5, 'มิ.ย.': 6,
        'ก.ค.': 7, 'ส.ค.': 8, 'ก.ย.': 9, 'ต.ค.': 10, 'พ.ย.': 11, 'ธ.ค.': 12,
        'มกราคม': 1, 'กุมภาพันธ์': 2, 'มีนาคม': 3, 'เมษายน': 4, 'พฤษภาคม': 5, 'มิถุนายน': 6,
        'กรกฎาคม': 7, 'สิงหาคม': 8, 'กันยายน': 9, 'ตุลาคม': 10, 'พฤศจิกายน': 11, 'ธันวาคม': 12
    }

    # 1. Handle YYYY-MM-DD or YYYY-MM-DD HH:MM:SS (standard ISO)
    try:
        if '-' in date_str and date_str.count('-') == 2:
            if ' ' in date_str or 'T' in date_str:
                iso_str = date_str.replace('T', ' ')
                return datetime.fromisoformat(iso_str)
            return datetime.strptime(date_str, "%Y-%m-%d")
    except: pass
    
    # 2. Handle Thai format with month names (e.g., "23 มิ.ย. 2558")
    import re
    # Match: Day Month Year [Time]
    # Use \S+ for month to capture Thai characters properly
    match = re.match(r'^(\d+)\s+(\S+)\s+(\d+)(?:\s+([\d:]+))?$', date_str)
    if match:
        day, month_name, year, time_part = match.groups()
        month = thai_months.get(month_name)
        if month:
            y = int(year)
            if y > 2400: y -= 543
            
            if time_part:
                # Handle HH:MM or HH:MM:SS
                t_parts = time_part.split(':')
                hour = int(t_parts[0])
                minute = int(t_parts[1]) if len(t_parts) > 1 else 0
                second = int(t_parts[2]) if len(t_parts) > 2 else 0
                return datetime(y, month, int(day), hour, minute, second)
            return datetime(y, month, int(day))

    # 3. Handle DD/MM/YYYY or D/M/Y (Thai BE)
    for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt == "%d/%m":
                dt = dt.replace(year=datetime.now().year)
            
            if dt.year > 2400:
                dt = dt.replace(year=dt.year - 543)
            elif fmt == "%d/%m/%y":
                if dt.year >= 2000:
                    dt = dt.replace(year=dt.year - 43)
                else: 
                    dt = dt.replace(year=dt.year + 57)
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
    now, fy = datetime.now(), get_current_fiscal_year()
    fy_str = str(fy)
    
    # 1. Get/Create Config
    config = query_db('SELECT * FROM TimelineConfig WHERE fiscal_year = ?', (fy_str,), one=True)
    if not config:
        execute_db('INSERT OR IGNORE INTO TimelineConfig (fiscal_year, start_date, end_date, rounds_json) VALUES (?,?,?,?)', 
                   (fy_str, "01/10", "30/09", "[]"))
        config = query_db('SELECT * FROM TimelineConfig WHERE fiscal_year = ?', (fy_str,), one=True)
    
    # 2. Results Initialization (Default: Closed, waiting for start of current fiscal year)
    is_open, reason, next_date = False, "ไม่อยู่ในช่วงเวลาการเปิดรับคำขอ", f"01/10/{fy}"
    s_main, e_main = parse_thai_date(config['start_date']), parse_thai_date(config['end_date'])

    # 3. Check Specific Rounds (High Priority)
    rounds = json.loads(config['rounds_json'] or '[]')
    for r in sorted(rounds, key=lambda x: parse_thai_date(x.get('start_date')) or datetime.max):
        s_dt = (parse_thai_date(r.get('start_date')) or now).replace(hour=0, minute=0)
        e_dt = (parse_thai_date(r.get('end_date')) or now).replace(hour=23, minute=59)
        
        if s_dt <= now <= e_dt:
            if r.get('type') == 'submission': return True, r.get('name', 'เปิดรับคำขอ'), None
            if r.get('type') == 'consideration': is_open, reason = False, r.get('name', 'ช่วงพิจารณา')
        elif s_dt > now and r.get('type') == 'submission' and not is_open:
            next_date = r['start_date']; break

    # 4. Global Range Check (Low Priority - only if no specific round applies)
    if is_open or reason == "ไม่อยู่ในช่วงเวลาการเปิดรับคำขอ":
        if s_main and e_main and s_main.replace(hour=0, minute=0) <= now <= e_main.replace(hour=23, minute=59):
            return True, "รอบการเปิดรับปกติ", None
        elif s_main and now < s_main:
            is_open, reason, next_date = False, "ยังไม่เปิดรับคำขอใหม่", config['start_date']

    # 5. Peek Logic for next year config if currently closed
    if not is_open:
        nxt = query_db('SELECT * FROM TimelineConfig WHERE fiscal_year = ?', (str(fy + 1),), one=True)
        if nxt:
            sub = [r for r in json.loads(nxt['rounds_json'] or '[]') if r.get('type') == 'submission']
            next_date = sub[0]['start_date'] if sub else nxt['start_date']

    return is_open, reason, next_date


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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_db('''
        INSERT INTO Notification (id, message, recipient_role, recipient_username, req_id, is_read, timestamp)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    ''', (notif_id, message, recipient_role, recipient_username, req_id, timestamp))


# ──────────────────────────────────────────────
# Compensation Calculation
# ──────────────────────────────────────────────

def calculate_compensation(works_list, position_str, fiscal_year_req):
    row = query_db('SELECT * FROM Criteria WHERE fiscal_year = ?', (str(fiscal_year_req),), one=True)
    if not row: row = query_db('SELECT * FROM Criteria ORDER BY fiscal_year DESC LIMIT 1', one=True)
    
    if row:
        qs = json.loads(row['quality_scores']) if row['quality_scores'] else {}
        rw = json.loads(row['role_weights']) if row['role_weights'] else {}
        pr = json.loads(row['payment_rules']) if row['payment_rules'] else {}
    else: qs, rw, pr = {}, {}, {}
    score_sum = 0
    
    # Use shared helper for position parsing
    positions = parse_academic_position(position_str)
    pos = " ".join(positions)

    # Improved position key detection with abbreviations
    pos_lower = pos.lower()
    if any(k in pos_lower for k in ['ผู้ช่วยศาสตราจารย์', 'ผศ.', 'ผศ']):
        pos_key = 'asst_prof'
    elif any(k in pos_lower for k in ['รองศาสตราจารย์', 'รศ.', 'รศ']):
        pos_key = 'assoc_prof'
    elif any(k in pos_lower for k in ['ศาสตราจารย์', 'ศ.', 'ศ']):
        pos_key = 'prof'
    else:
        pos_key = ''
    
    for w in works_list:
        w_type, details = w.get('type'), w.get('details', {})
        s, weight = 0.0, 0.0
        
        # 1. Base Score (S)
        if w_type == 'research':
            db_map = {'scopus_q1_q2': 'tier1', 'scopus_other': 'non_q', 'national': 'national'}
            db_key = db_map.get(details.get('database'))
            if db_key:
                s = qs.get('research', {}).get(db_key, 0.0)
            else:
                s = 0.0
        elif w_type in ['social', 'industry', 'teaching', 'policy', 'innovation'] or w_type.startswith('custom_'):
            lvl_map = {'level_a_plus': 'a_plus', 'level_a': 'a', 'level_b': 'b'}
            lvl_key = lvl_map.get(details.get('level'))
            if lvl_key:
                s = qs.get('merged_abc', {}).get(lvl_key, 0.0)
            else:
                s = 0.0
        elif w_type == 'textbook':
            pt = details.get('publish_type')
            if pt == 'inter':
                s = qs.get('textbook', {}).get('publisher', 0.0)
            elif pt == 'local':
                s = qs.get('textbook', {}).get('general', 0.0)
            else:
                s = 0.0
        elif w_type == 'creative':
            cre_map = {'inter': 'international', 'coop': 'cooperation', 'national': 'national'}
            pt = details.get('publish_type', '')
            found_key = next((k for k in cre_map if k in pt), None)
            if found_key:
                s = qs.get('creative', {}).get(cre_map[found_key], 0.0)
            else:
                s = 0.0
        
        # 2. Weight (W)
        contrib = details.get('contribution')
        if contrib in ['first', 'corresponding', 'main']:
            weight = rw.get('main', 0.0)
        elif contrib in ['intellectual', 'co']:
            weight = rw.get('co', 0.0)
        else:
            weight = 0.0
            
        net = s * weight
        
        # Always update breakdown with the formula
        w.update({'base_score': s, 'weight': weight, 'score_breakdown': f"ฐาน {s} x น้ำหนัก {weight}"})
        
        # 3. Apply status logic for actual score
        if w.get('status') in ['ไม่อนุมัติ', 'ผลงานซ้ำซ้อน']:
            w.update({'score_calc': 0, 'payment_calc': 0})
        else:
            # Only use calculated score if no manual score (score_calc) exists 
            # or if score_calc is 0 (except for rejected items)
            existing_score = w.get('score_calc')
            final_score = float(existing_score) if existing_score is not None and existing_score != 0 else net
            
            w.update({'score_calc': final_score, 'payment_calc': 0})
            score_sum += final_score

    # 3. Calculate compensation based on Tiers
    comp = 0
    if pos_key and pr.get(pos_key):
        tiers = pr[pos_key]
        applicable = [t for t in (tiers if isinstance(tiers, list) else [tiers]) if score_sum >= float(t.get('min_score', 0))]
        if applicable:
            comp = float(sorted(applicable, key=lambda x: float(x.get('min_score', 0)))[-1].get('amount', 0))

    return score_sum, comp