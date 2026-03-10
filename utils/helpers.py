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
    except (json.JSONDecodeError, TypeError):
        return []


def load_config(filename, default=None):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, TypeError, OSError):
        return default


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

def safe_int(val, default=None):
    """แปลงเป็น int ได้อย่างปลอดภัย คืน default ถ้าแปลงไม่ได้"""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_json_loads(val, default=None):
    """Parse JSON ด้วย default เมื่อ invalid"""
    if not val:
        return default if default is not None else []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def deserialize_request(row):
    """แปลง row จาก DB (sqlite3.Row) เป็น dict พร้อม works, applicant_info, etc."""
    req = dict(row)
    req['works'] = _safe_json_loads(req.get('works_json'), [])
    req['applicant_info'] = _safe_json_loads(req.get('applicant_info_json'), {})
    req['audit_trail'] = _safe_json_loads(req.get('history_json'), [])
    req['applicant'] = req['applicant_username']  # Compatibility alias
    req['date'] = req['date_submitted']            # Compatibility alias
    req['score'] = req['total_score']              # Compatibility alias
    return req


def parse_criteria_row(row):
    """แปลง Criteria row จาก DB ให้มี quality_scores, role_weights, payment_rules เป็น dict"""
    if not row:
        return None
    d = dict(row)
    for key in ('quality_scores', 'role_weights', 'payment_rules'):
        try:
            d[key] = json.loads(d[key]) if d.get(key) else {}
        except (json.JSONDecodeError, TypeError):
            d[key] = {}
    return d


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
    except (ValueError, TypeError):
        pass
    
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
        except (ValueError, TypeError):
            continue
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
    config = query_db('SELECT * FROM TimelineConfig WHERE fiscal_year = ?', (str(current_fy),), one=True)
    if not config:
        config = query_db('SELECT * FROM TimelineConfig ORDER BY fiscal_year DESC LIMIT 1', one=True)
        
    if not config:
        return True, "", None # Default open

    now = datetime.now()
    rounds = json.loads(config['rounds_json']) if config['rounds_json'] else []
    
    active_submission_round = None
    active_consideration_round = None
    next_submission_round = None
    
    # Sort rounds by start date to find the next opening easily
    sorted_rounds = sorted(rounds, key=lambda x: parse_thai_date(x.get('start_date')) or datetime.max)
    
    for r in sorted_rounds:
        s_dt = parse_thai_date(r.get('start_date'))
        e_dt = parse_thai_date(r.get('end_date'))
        if s_dt and e_dt:
            s_dt = s_dt.replace(hour=0, minute=0, second=0)
            e_dt = e_dt.replace(hour=23, minute=59, second=59)
            
            if s_dt <= now <= e_dt:
                if r.get('type') == 'submission':
                    active_submission_round = r
                elif r.get('type') == 'consideration':
                    active_consideration_round = r
            elif s_dt > now and r.get('type') == 'submission':
                if not next_submission_round:
                    next_submission_round = r

    # Priority 1: Submission round is active
    if active_submission_round:
        return True, active_submission_round.get('name', 'ช่วงเปิดรับคำขอ'), None
    
    # Priority 2: Consideration round is active
    if active_consideration_round:
        # Use next defined submission round OR fallback to start of next fiscal year
        next_date = next_submission_round.get('start_date') if next_submission_round else f"01/10/{current_fy}"
        return False, active_consideration_round.get('name', 'ช่วงปิดรับคำขอ'), next_date

    # Priority 3: Fallback to global range
    dt_main_start = parse_thai_date(config['start_date'])
    dt_main_end = parse_thai_date(config['end_date'])
    
    if dt_main_start and dt_main_end:
        dt_main_start = dt_main_start.replace(hour=0, minute=0, second=0)
        dt_main_end = dt_main_end.replace(hour=23, minute=59, second=59)
        if dt_main_start <= now <= dt_main_end:
            return True, "รอบการเปิดรับปกติ", None
        elif now < dt_main_start:
            return False, "ยังไม่เปิดรับคำขอใหม่", config['start_date']
        else:
            # Already passed main end date, next opening is next FY
            return False, "ไม่อยู่ในช่วงเวลาการเปิดรับคำขอ", f"01/10/{current_fy}"

    return True, "", None


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
    row = query_db('SELECT * FROM Criteria WHERE fiscal_year = ?', (str(fiscal_year_req),), one=True)
    if not row:
        row = query_db('SELECT * FROM Criteria ORDER BY fiscal_year DESC LIMIT 1', one=True)
    crit = parse_criteria_row(row)
    qs = crit.get('quality_scores', {}) if crit else {}
    rw = crit.get('role_weights', {}) if crit else {}
    pr = crit.get('payment_rules', {}) if crit else {}
    score_sum = 0
    
    # Use shared helper for position parsing
    positions = parse_academic_position(position_str)
    pos_key = _get_pos_key(positions)

    for w in works_list:
        w_type, details = w.get('type'), w.get('details', {})
        s, weight = 0.0, 0.0
        
        # 1. Base Score (S)
        if w_type == 'research':
            db_map = {'scopus_q1_q2': 'tier1', 'scopus_other': 'non_q', 'national': 'national'}
            s = qs.get('research', {}).get(db_map.get(details.get('database'), 'national'), 0.75)
        elif w_type in ['social', 'industry', 'teaching', 'policy', 'innovation'] or w_type.startswith('custom_'):
            lvl_map = {'level_a_plus': 'a_plus', 'level_a': 'a', 'level_b': 'b'}
            s = qs.get('merged_abc', {}).get(lvl_map.get(details.get('level'), 'a'), 1.0)
        elif w_type == 'textbook':
            s = qs.get('textbook', {}).get('publisher' if details.get('publish_type') != 'local' else 'general', 1.25)
        elif w_type == 'creative':
            cre_map = {'inter': 'international', 'coop': 'cooperation', 'national': 'national'}
            pt = details.get('publish_type', '')
            found_key = next((k for k in cre_map if k in pt), 'inter')
            s = qs.get('creative', {}).get(cre_map[found_key], 1.25)
        
        # 2. Weight (W)
        weight = rw.get('main' if details.get('contribution') in ['first', 'corresponding', 'main'] else 'co', 0.0)
        net = s * weight
        
        # Always update breakdown with the formula
        w.update({'base_score': s, 'weight': weight, 'score_breakdown': f"ฐาน {s} x น้ำหนัก {weight}"})

        if w.get('status') in ['ไม่อนุมัติ', 'ผลงานซ้ำซ้อน']:
            w.update({'score_calc': 0, 'payment_calc': 0})
        else:
            w.update({'score_calc': net, 'payment_calc': 0})
            score_sum += net

    # 3. Calculate compensation based on Tiers
    comp = 0
    if pos_key and pr.get(pos_key):
        tiers = pr[pos_key]
        applicable = [t for t in (tiers if isinstance(tiers, list) else [tiers]) if score_sum >= float(t.get('min_score', 0))]
        if applicable:
            comp = float(sorted(applicable, key=lambda x: float(x.get('min_score', 0)))[-1].get('amount', 0))

    return score_sum, comp


def _get_pos_key(positions):
    """แปลงตำแหน่งวิชาการเป็น key สำหรับ payment_rules"""
    pos = " ".join(positions) if isinstance(positions, list) else str(positions)
    if 'ผู้ช่วยศาสตราจารย์' in pos:
        return 'asst_prof'
    if 'รองศาสตราจารย์' in pos:
        return 'assoc_prof'
    if 'ศาสตราจารย์' in pos:
        return 'prof'
    return ''


def recalculate_total_only(works_list, position_str, fiscal_year_req):
    """
    Recalculates total score and compensation based on EXISTING score_calc of each work.
    Does NOT recalculate base scores from criteria, effectively preserving any manual score edits.
    """
    row = query_db('SELECT * FROM Criteria WHERE fiscal_year = ?', (str(fiscal_year_req),), one=True)
    if not row:
        row = query_db('SELECT * FROM Criteria ORDER BY fiscal_year DESC LIMIT 1', one=True)
    crit = parse_criteria_row(row)
    pr = crit.get('payment_rules', {}) if crit else {}
    score_sum = 0
    pos_key = _get_pos_key(parse_academic_position(position_str))
    
    for w in works_list:
        if w.get('status') in ['ไม่อนุมัติ', 'ผลงานซ้ำซ้อน']:
            w['payment_calc'] = 0
            # Do NOT reset score_calc to 0 in memory, just don't add to sum
            # Actually, standard logic sets score_calc=0 for rejected items in the return draft.
            # To be safe, we don't modify the work object here, just skip adding to sum.
            pass
        else:
            w['payment_calc'] = 0
            score_sum += float(w.get('score_calc', 0))
            
    comp = 0
    if pos_key and pr.get(pos_key):
        tiers = pr[pos_key]
        applicable = [t for t in (tiers if isinstance(tiers, list) else [tiers]) if score_sum >= float(t.get('min_score', 0))]
        if applicable:
            comp = float(sorted(applicable, key=lambda x: float(x.get('min_score', 0)))[-1].get('amount', 0))

    return score_sum, comp