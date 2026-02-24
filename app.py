import flask
from werkzeug.utils import secure_filename
import json
import os
from datetime import datetime
import tempfile
from database import init_db, query_db, execute_db

app = Flask(__name__)
app.secret_key = "academic_secret_key"

# Initialize database
init_db()

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'zip', 'rar'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    # Handle YYYY-MM-DD (standard HTML5 date input)
    try:
        if '-' in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except: pass
    
    # Handle DD/MM/YYYY (Thai BE)
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        # If year is B.E. (e.g. 2569), convert to A.D. for internal logic
        if dt.year > 2400:
            dt = dt.replace(year=dt.year - 543)
        return dt
    except: return None

def is_within_timeline():
    # Load list of timelines
    timelines = load_config('timeline.json', [])
    if not isinstance(timelines, list):
        # Legacy single object support (convert if needed)
        if isinstance(timelines, dict):
            timelines = [{"fiscal_year": "2569", **timelines}]
        else:
            return True # Fallback

    current_fy = get_current_fiscal_year()
    # Find timeline for CURRENT fiscal year
    timeline = next((t for t in timelines if str(t.get('fiscal_year')) == str(current_fy)), None)
    
    if not timeline or not timeline.get('start_date') or not timeline.get('end_date'):
        return True # Default to open if not configured for this year
    
    try:
        now = datetime.now()
        current_val = now.month * 100 + now.day
        
        start_d, start_m = map(int, timeline['start_date'].split('/'))
        end_d, end_m = map(int, timeline['end_date'].split('/'))
        
        start_val = start_m * 100 + start_d
        end_val = end_m * 100 + end_d
        
        if start_val <= end_val:
            return start_val <= current_val <= end_val
        else:
            return current_val >= start_val or current_val <= end_val
    except:
        return True

def get_remaining_days(start_date_str, limit_days=7):
    if not start_date_str: return limit_days
    start_dt = parse_thai_date(start_date_str)
    if not start_dt: return limit_days
    delta = datetime.now() - start_dt
    return limit_days - delta.days

def get_current_fiscal_year():
    today = datetime.now()
    # Fiscal Year Rule: Starts Oct 1 of Year X-1 ends Sep 30 of Year X -> FY X
    if today.month >= 10:
        return today.year + 543 + 1
    return today.year + 543

def create_notification(message, recipient_role=None, recipient_username=None, req_id=None):
    notif_id = f"NOTIF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
    timestamp = format_thai_date(datetime.now(), True)
    execute_db('''
        INSERT INTO Notification (id, message, recipient_role, recipient_username, req_id, is_read, timestamp)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    ''', (notif_id, message, recipient_role, recipient_username, req_id, timestamp))

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

@app.route('/') # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว (หน้าแรก)
def index():
    if 'username' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))
@app.context_processor
def inject_timeline():
    can_submit = is_within_timeline()
    timelines = load_config('timeline.json', [])
    current_fy = str(get_current_fiscal_year())
    
    # Get the specific timeline for alerting
    if isinstance(timelines, list):
        tl = next((t for t in timelines if str(t.get('fiscal_year')) == current_fy), {})
    else:
        tl = timelines # Legacy
        
    has_submitted = False
    if 'username' in session and session['role'] == 'applicant':
        all_reqs = load_data('requests.json')
        # Check if user has any non-draft request in the current fiscal year
        user_reqs = [r for r in all_reqs if r['applicant'] == session['username'] and str(r.get('fiscal_year')) == current_fy]
        if any(r.get('status') != 'แบบร่าง' for r in user_reqs):
            has_submitted = True
            
    return dict(can_submit=can_submit, timeline=tl, has_submitted_this_year=has_submitted)

@app.template_filter('role_status_label')
def role_status_label(status, role):
    # Admin (Administration)
    if role == 'administration':
        if status == 'ส่งแล้ว': return 'รอตรวจสอบ'
        if status == 'แก้ไข': return 'ส่งคืนแก้ไขแล้ว'
        if status == 'รอตรวจประวัติการยื่นขอ': return 'ส่งให้งานวิจัยแล้ว'
        if status == 'ผลงานผ่าน': return 'รอคำนวนค่าตอบแทน'
        if status == 'ผลงานซ้ำซ้อน': return 'ผลงานเคยถูกใช้แล้ว'
        if status == 'ซ้ำซ้อนบางส่วน': return 'ซ้ำซ้อนบางส่วน'
        if status == 'รอเสนอพิจารณา': return 'รอจัดชุด (พร้อมเสนอ)'
        if status == 'อยู่ในรอบพิจารณา': return 'เสนอคณะกรรมการแล้ว'

    # Research
    if role == 'research':
        if status == 'รอตรวจประวัติการยื่นขอ': return 'รอตรวจสอบ'
        if status == 'ผลงานผ่าน': return 'ไม่เคยใช้'
        if status == 'ผลงานซ้ำซ้อน': return 'เคยใช้แล้ว'
        if status == 'ซ้ำซ้อนบางส่วน': return 'ซ้ำซ้อนบางส่วน'

    # Committee
    if role == 'committee':
        if status == 'อยู่ในรอบพิจารณา': return 'รอการพิจารณา (ในรอบ)'
        if status == 'รอการพิจารณา': return 'รอการพิจารณา' # Legacy fallback
        if status == 'รอการอุทธรณ์': return 'รอพิจารณาอุทธรณ์'

    # Applicant
    if role == 'applicant':
        if status == 'ส่งแล้ว': return 'ส่งแล้ว'
        if status == 'รอตรวจประวัติการยื่นขอ': return 'กำลังตรวจสอบคำขอ'
        if status == 'ผลงานผ่าน': return 'ผ่าน (รอเจ้าหน้าที่งานบุคคลส่งรอบพิจารณา)'
        if status == 'ผลงานซ้ำซ้อน': return 'ผลงานเคยถูกใช้แล้ว'
        if status == 'ซ้ำซ้อนบางส่วน': return 'ซ้ำซ้อนบางส่วน'
        if status == 'อยู่ในรอบพิจารณา': return 'รอผลการพิจารณา (รอบ)'
        if status == 'รอการพิจารณา': return 'รอการพิจารณา'
    
    if status == 'ยกเลิก': return 'ยกเลิก'

    # Default fallback
    return status

@app.route('/view_work/<req_id>/<int:work_index>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุภวัฒน์ ไกรษี (ตรวจสอบคำขอ)
def view_work(req_id, work_index):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    requests_list = load_data('requests.json')
    req = next((r for r in requests_list if r['id'] == req_id), None)
    if not req:
        return "Request not found", 404
    
    if request.method == 'POST':
        if session['role'] != 'administration':
            flash("คุณไม่มีสิทธิ์แก้ไขข้อมูลนี้")
            return redirect(url_for('view_work', req_id=req_id, work_index=work_index))
        
        # Admin is updating work details
        work = req['works'][work_index]
        
        # Update details based on work type - ONLY ALLOW LEVEL UPDATES AS REQUESTED (for A+, A, B choices)
        if work['type'] in ['social', 'industry', 'teaching', 'policy', 'innovation']:
            if 'level' in request.form:
                work['details']['level'] = request.form.get('level')
            
        # Recalculate compensation for the whole request since one work changed
        new_total_score, new_total_comp = calculate_compensation(
            req['works'], 
            req['applicant_info'].get('academic_position', ''),
            req.get('fiscal_year', '')
        )
        req['total_score'] = new_total_score
        req['total_compensation'] = new_total_comp
        
        save_data('requests.json', requests_list)
        flash("แก้ไขข้อมูลผลงานและคำนวณคะแนนใหม่เรียบร้อยแล้ว")
        return redirect(url_for('view_work', req_id=req_id, work_index=work_index))

    # Get the user who submitted this request to show their profile info
    users_list = load_data('users.json')
    applicant_user = next((u for u in users_list if u['username'] == req['applicant']), None)

    # Authorization Check
    if session['role'] == 'applicant' and req['applicant'] != session['username']:
        flash("คุณไม่มีสิทธิ์เข้าถึงข้อมูลนี้")
        return redirect(url_for('dashboard'))
    
    return render_template('view_work.html', 
                          name=session['name'], 
                          role=session['role'], 
                          position=session.get('position', ''),
                          req=req,
                          user=applicant_user,
                          work_index=work_index)

@app.template_filter('rich_status_label')
def rich_status_label(req, role):
    status = req.get('status', '')
    if status == 'อนุมัติ':
        # Check if any individual work was rejected
        works = req.get('works', [])
        has_rejected = any(w.get('status') in ['ไม่อนุมัติ', 'ผลงานซ้ำซ้อน'] for w in works)
        if has_rejected:
            return 'อนุมัติ (ไม่อนุญาตบางส่วน)'
    
    # Fallback to standard role-based logic
    return role_status_label(status, role)

@app.template_filter('translate_work_type')
def translate_work_type(initial_type):
    mapping = {
        'research': 'บทความงานวิจัย',
        'textbook': 'ตำราหรือหนังสือ',
        'creative': 'งานสร้างสรรค์',
        'social': 'ผลงานรับใช้ท้องถิ่นและสังคม',
        'industry': 'ผลงานวิชาการเพื่ออุตสาหกรรม',
        'teaching': 'ผลงานการสอน',
        'policy': 'ผลงานวิชาการเพื่อพัฒนานโยบายสาธารณะ',
        'innovation': 'ผลงานนวัตกรรม'
    }
    return mapping.get(initial_type, initial_type)

@app.template_filter('translate_contribution')
def translate_contribution(role):
    mapping = {
        'first': 'ผู้ประพันธ์อันดับแรก (First Author)',
        'corresponding': 'ผู้ประพันธ์บรรณกิจ (Corresponding Author)',
        'main': 'ผู้ดำเนินการหลัก (Main Author)',
        'intellectual': 'ผู้มีส่วนสำคัญทางปัญญา (Intellectual Contributor)',
        'co': 'ผู้ดำเนินการร่วม (Co-Author)'
    }
    return mapping.get(role, role)

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
        
        elif w_type in ['social', 'industry', 'teaching', 'policy', 'innovation']:
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


# ... [Existing Routes] ...
# Make sure to place this before other routes or search appropriately for placement.
# We will insert new routes at end of file usually, or organized.
# But for `replace_file_content` targeting, I will put it around where `view_request` is or at the end.
# Actually I need to match existing code structure.

# Let's modify the `view_request` Admin Action logic first (inside view_request function)
# I will use multi_replace for that separately if needed, but here I'm instructed to add routes.
# I will add routes at the end of file.

@app.route('/manage/rounds', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายกฤษฎา ตะเคียนเกลี้ยง (สร้างรอบพิจารณา)
def manage_rounds():
    if 'username' not in session or session['role'] not in ['administration', 'committee', 'admin']: # Committee might want to see history
         return redirect(url_for('login'))
         
    all_reqs = load_data('requests.json')
    batches = load_data('batches.json')
    
    # Filter pending requests (Ready for Batching)
    pending_reqs = [r for r in all_reqs if r.get('status') == 'รอเสนอพิจารณา']
    
    if request.method == 'POST' and session['role'] == 'administration':
        action = request.form.get('action')
        if action == 'create_round':
            req_ids = request.form.getlist('req_ids')
            # Get Fiscal Year from the first request in the batch
            batch_fy = ""
            if req_ids:
                first_req = next((r for r in all_reqs if r['id'] == req_ids[0]), None)
                if first_req:
                    batch_fy = first_req.get('fiscal_year', '')

            round_name = f"รายงานคำขอ รอบปีงบประมาณ {batch_fy}"

            # Create Batch
            new_batch = {
                "id": f"ROUND-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "name": round_name,
                "meeting_date": request.form.get('meeting_date'),
                "fiscal_year": batch_fy,
                "created_date": format_thai_date(datetime.now(), True),
                "status": "รอการพิจารณา",
                "req_ids": req_ids
            }
            batches.insert(0, new_batch) # Newest first
            save_data('batches.json', batches)
            
            # Update Requests Status
            for r in all_reqs:
                if r['id'] in req_ids:
                    r['status'] = 'อยู่ในรอบพิจารณา'
                    r['batch_id'] = new_batch['id']
            save_data('requests.json', all_reqs)
            
            flash(f"สร้างรอบการพิจารณาเรียบร้อยแล้ว")
            return redirect(url_for('round_history'))

    return render_template('create_round.html', name=session['name'], role=session['role'], position=session.get('position',''), pending_reqs=pending_reqs)

@app.route('/round_history') # ผู้รับผิดชอบ: นายกฤษฎา ตะเคียนเกลี้ยง (สร้างรอบพิจารณา)
def round_history():
    if 'username' not in session or session['role'] not in ['administration', 'committee', 'admin']: 
         return redirect(url_for('login'))
         
    batches = load_data('batches.json')
    return render_template('round_history.html', name=session['name'], role=session['role'], position=session.get('position',''), batches=batches)

@app.route('/view_round/<round_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายกฤษฎา ตะเคียนเกลี้ยง (สร้างรอบพิจารณา)
def view_round(round_id):
    if 'username' not in session: return redirect(url_for('login'))
    
    batches = load_data('batches.json')
    batch = next((b for b in batches if b['id'] == round_id), None)
    if not batch:
        flash("ไม่พบข้อมูลรอบการพิจารณา")
        return redirect(url_for('dashboard'))
        
    all_reqs = load_data('requests.json')
    target_reqs = [r for r in all_reqs if r['id'] in batch['req_ids']]
    
    # Calculate Summary
    users = load_data('users.json')
    eligible_count = len([u for u in users if u['role'] == 'applicant'])
    
    # Applicant Count (Unique in this batch)
    applicants_in_batch = set(r['applicant'] for r in target_reqs)
    
    total_amount = sum(float(r.get('approved_amount', 0) or 0) for r in target_reqs)
    
    works_breakdown = []
    for r in target_reqs:
        for idx, w in enumerate(r.get('works', [])):
            # Skip duplicate works for committee
            if w.get('status') == 'ผลงานซ้ำซ้อน':
                continue
                
            works_breakdown.append({
                "req_id": r['id'],
                "work_index": idx,
                "applicant": r['applicant'],
                "name": r['applicant_name'],
                "position": r['applicant_info'].get('academic_position', '-'),
                "department": r['applicant_info'].get('department', '-'),
                "work_title": w['details'].get('title', '-'),
                "work_type": w.get('type', '-'),
                "score": w.get('score_calc', 0),
                "amount": w.get('payment_calc', 0),
                "status": w.get('status', r['status']),
                "comment": w.get('comment', '')
            })
    
    # Calculate Summary stats
    users = load_data('users.json')
    eligible_count = len([u for u in users if u['role'] == 'applicant'])
    applicants_in_batch = set(r['applicant'] for r in target_reqs)
    total_amount = sum(float(r.get('approved_amount', 0) or 0) for r in target_reqs)
    
    summary = {
        "applicant_count": len(applicants_in_batch),
        "total_eligible": eligible_count,
        "request_count": len(works_breakdown), # Now count works
        "total_amount": total_amount,
        "works_breakdown": works_breakdown
    }

    if request.method == 'POST' and session['role'] == 'committee':
        action = request.form.get('action')
        if action == 'announce_results':
            batch['status'] = 'ประกาศผลแล้ว'
            
            # Update individual requests and works
            for r in target_reqs:
                all_works_approved = True
                any_work_rejected = False
                
                # Update individual work statuses based on form
                for idx, w in enumerate(r.get('works', [])):
                    decision = request.form.get(f"status_{r['id']}_{idx}")
                    comment = request.form.get(f"comment_{r['id']}_{idx}")
                    
                    if decision == 'approve':
                        w['status'] = 'อนุมัติ'
                    elif decision == 'reject':
                        w['status'] = 'ไม่อนุมัติ'
                        w['comment'] = comment or "ไม่อนุมัติ"
                        all_works_approved = False
                        any_work_rejected = True

                # RE-CALCULATE COMPENSATION for the request based on approved works only
                approved_works = [w for w in r.get('works', []) if w.get('status') == 'อนุมัติ']
                
                # Calculate total score from approved works
                effective_score, final_comp = calculate_compensation(
                    approved_works, 
                    r['applicant_info'].get('academic_position', ''), 
                    r.get('fiscal_year')
                )
                
                # Update Request level status
                if len(approved_works) == len(r.get('works', [])):
                    r['status'] = 'อนุมัติ'
                elif len(approved_works) > 0:
                    r['status'] = 'อนุมัติบางส่วน'
                else:
                    r['status'] = 'ไม่อนุมัติ'
                
                r['approved_amount'] = final_comp
                r['score'] = effective_score # Update current score based on approved items

            save_data('batches.json', batches)
            save_data('requests.json', all_reqs)
            
            flash("ประกาศผลการพิจารณาเรียบร้อยแล้ว")
            return redirect(url_for('dashboard'))

    return render_template('view_round.html', batch=batch, summary=summary, role=session['role'])



@app.route('/login', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นาย ธนวรรธ ทองตื้อ (เข้าสู่ระบบ)
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        user = query_db('SELECT * FROM User WHERE username = ? AND password = ?', (username, password), one=True)
        if user:
            session.update({
                'username': user['username'], 
                'role': user['role'], 
                'name': f"{user['title_name'] or ''} {user['name'] or ''}".strip(),
                'position': user['academic_position'] or {
                    'admin': 'ผู้ดูแลระบบ',
                    'administration': 'เจ้าหน้าที่งานบุคคล',
                    'research': 'เจ้าหน้าที่งานวิจัย',
                    'committee': 'คณะกรรมการประจำคณะ',
                    'applicant': 'ผู้ยื่นคำขอ'
                }.get(user['role'], user['role'])
            })
            return redirect(url_for('dashboard'))
        else:
            flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return render_template('login.html')

@app.route('/api/notifications') # ผู้รับผิดชอบ: นายฤทธิชัย โสนะกาล (แจ้งเตือน)
def get_notifications():
    if 'username' not in session: return jsonify([])
    
    # Query database for notifications
    notifs = query_db('''
        SELECT * FROM Notification 
        WHERE is_read = 0 
        AND (recipient_username = ? OR recipient_role = ?)
        ORDER BY timestamp DESC
    ''', (session['username'], session['role']))
    
    result = []
    for n in notifs:
        result.append({
            "id": n['id'],
            "message": n['message'],
            "req_id": n['req_id'],
            "timestamp": n['timestamp']
        })
    return jsonify(result)

@app.route('/api/notifications/read/<notif_id>', methods=['POST']) # ผู้รับผิดชอบ: นายฤทธิชัย โสนะกาล (แจ้งเตือน)
def read_notification(notif_id):
    if 'username' not in session: return jsonify({"success": False})
    execute_db('UPDATE Notification SET is_read = 1 WHERE id = ?', (notif_id,))
    return jsonify({"success": True})

@app.route('/notifications') # ผู้รับผิดชอบ: นายฤทธิชัย โสนะกาล (แจ้งเตือน)
def notifications_page():
    if 'username' not in session: return redirect(url_for('login'))
    notifs = load_data('notifications.json')
    
    # Filter for user
    user_notifs = [
        n for n in notifs 
        if n.get('recipient_username') == session['username'] or
           (n.get('recipient_role') and n.get('recipient_role') == session['role'])
    ]
    
    return render_template('notifications.html', name=session['name'], role=session['role'], position=session.get('position',''), notifications=user_notifs)

@app.route('/appeals') # ผู้รับผิดชอบ: นางสาวเบญจมาศ จ่านันท์ (ยื่นอุทธรณ์)
def appeals_page():
    if 'username' not in session or session['role'] not in ['committee', 'applicant']:
        return redirect(url_for('login'))
    
    all_reqs = load_data('requests.json')
    # Filter for appeal statuses
    if session['role'] == 'committee':
        appeal_reqs = [r for r in all_reqs if r.get('status') in ['รอการอุทธรณ์', 'ยื่นอุทธรณ์', 'กำลังพิจารณาอุทธรณ์', 'รอพิจารณาอุทธรณ์']]
    else:
        # Applicant sees their own appeals
        appeal_reqs = [r for r in all_reqs if r['applicant'] == session['username'] and r.get('status') == 'รอการอุทธรณ์']
    
    return render_template('appeals.html', name=session['name'], role=session['role'], position=session.get('position',''), requests=appeal_reqs)

@app.route('/dashboard') # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว (ค้นหาคำขอ)
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    
    all_reqs = load_data('requests.json')
    batches = load_data('batches.json')
    pending_reqs = []
    
    if session['role'] == 'applicant':
        display_reqs = [r for r in all_reqs if r['applicant'] == session['username']]
    elif session['role'] in ['administration', 'research', 'committee']:
        # Show all non-draft requests
        display_reqs = [r for r in all_reqs if r['status'] != 'แบบร่าง']
        if session['role'] == 'administration':
            pending_reqs = [r for r in all_reqs if r.get('status') == 'รอเสนอพิจารณา']
    else:
        display_reqs = []
    
    # Load users for admin role
    all_users = []
    if session['role'] == 'admin':
        all_users = load_data('users.json')
    
    return render_template('dashboard.html', name=session['name'], role=session['role'], position=session.get('position',''), requests=display_reqs, batches=batches, pending_reqs=pending_reqs, users=all_users)

@app.route('/new_request', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ (ผู้ยื่น/แบบฟอร์ม)
def new_request():
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('login'))
    
    can_submit = is_within_timeline()
    if not can_submit:
        flash("ไม่อยู่ในช่วงเวลาที่เปิดรับคำขอ")
        return redirect(url_for('dashboard'))
    
    criteria = load_config('criteria.json', [])

    fiscal_year = get_current_fiscal_year()
    
    users = load_data('users.json')
    user_profile = next((u for u in users if u['username'] == session['username']), {})

    # Check for edit mode
    edit_id = request.args.get('edit_id')
    edit_req = None
    if edit_id:
        all_reqs = load_data('requests.json')
        edit_req = next((r for r in all_reqs if r['id'] == edit_id and r['applicant'] == session['username']), None)
    else:
        # Enforce one submission per year rule for new requests
        all_reqs = load_data('requests.json')
        current_fy = str(fiscal_year)
        existing_req = next((r for r in all_reqs if r['applicant'] == session['username'] 
                            and str(r.get('fiscal_year')) == current_fy), None)
        
        if existing_req:
            if existing_req.get('status') == 'แบบร่าง':
                # If they have a draft, redirect to it instead of blocking
                return redirect(url_for('new_request', edit_id=existing_req['id']))
            else:
                flash("คุณได้ยื่นคำขอไปแล้วในปีงบประมาณนี้ สามารถยื่นได้เพียงปีละ 1 ครั้งเท่านั้น")
                return redirect(url_for('dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')
        
        # Handle traditional form submit or checks
        if action == 'submit' and not can_submit:
             flash("ไม่อยู่ในช่วงเวลาที่เปิดรับคำขอ")
             return redirect(url_for('new_request'))

        # Prepare Request Data
        # For this complex form, we expect works to be gathered via JS and sent as JSON or structured form data
        # Let's assume we handle standard form submission but parse dynamic fields
        
        # Basic Info
        req_id = request.form.get('req_id') or f"REQ-{datetime.now().strftime(f'%Y{to_thai_year(datetime.now())}%m%d%H%M%S')}"
        # Actually standard REQ ID usually uses AD or specific format. 
        # User asked "Change AD to BE system". REQ ID often keeps sortable AD YYYY. 
        # But let's use BE Year in ID as requested? "REQ-2569..." might be confusing if sorted by strict string 
        # but locally fine. Let's stick to simple YYYYMMDD... but using BE?
        # Let's adjust REQ ID to use BE year: f"REQ-{year+543}..."
        now_dt = datetime.now()
        req_id = request.form.get('req_id') or f"REQ-{now_dt.year + 543}{now_dt.strftime('%m%d%H%M%S')}"
        
        # Works Processing
        works_json = request.form.get('works_data')
        works = json.loads(works_json) if works_json else []

        # Handle File Uploads for each work
        for w in works:
            work_id = w.get('details', {}).get('id')
            if not work_id: continue
            
            file_key = f'evidence_file_{work_id}'
            if file_key in request.files:
                file = request.files[file_key]
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Create directory for this request and work
                    save_dir = os.path.join(app.config['UPLOAD_FOLDER'], req_id, str(work_id))
                    os.makedirs(save_dir, exist_ok=True)
                    file_path = os.path.join(save_dir, filename)
                    file.save(file_path)
                    w['details']['evidence_type'] = 'file'
                    w['details']['evidence_file'] = filename
                elif w['details'].get('evidence_type') == 'file':
                    # If it was already a file and no new file uploaded, keep it
                    # (This handles the case when editing a request)
                    pass
            # If evidence_type is 'link', it will be handled by the JSON data already

        total_score = 0
        suggested_compensation = 0
        
        # Helper Function for Calculation was moved to global scope


        # Run Calculation
        user_position_from_form = request.form.get('academic_position', '')
        # Fallback to profile if form data is empty (unlikely with required field)
        academic_position_to_use = user_position_from_form if user_position_from_form else user_profile.get('academic_position', '')
        
        req_fy = request.form.get('fiscal_year_req')
        total_score, suggested_compensation = calculate_compensation(works, academic_position_to_use, req_fy)
        
        req_data = {
            "id": req_id,
            "applicant": session['username'],
            "applicant_name": session['name'],
            "applicant_info": {
                "title_name": user_profile.get('title_name', ''),
                "academic_position": academic_position_to_use, # Use the submitted position
                "position_date": user_profile.get('position_date', ''),
                "position_number": user_profile.get('position_number', ''),
                "department": user_profile.get('department', ''),
                "faculty": user_profile.get('faculty', '')
            },
            "fiscal_year": request.form.get('fiscal_year_req'),
            "works": works,
            "date": format_thai_date(datetime.now(), True),
            "status": "ส่งแล้ว" if action == "submit" else "แบบร่าง",
            "score": total_score, 
            "suggested_compensation": suggested_compensation,
            "comment": "",
            "timeline_status": "ontime" if can_submit else "late",
            "certify": True if request.form.get('certify') else False
        }
        
        if action == "submit":
            create_notification(f"มีคำขอใหม่ {req_id} จาก {session['name']}", recipient_role='administration', req_id=req_id)
        
        all_reqs = load_data('requests.json')
        
        # Update if exists, else append
        existing_idx = next((i for i, r in enumerate(all_reqs) if r['id'] == req_id), -1)
        if existing_idx > -1:
            # Preserve some fields if needed, or just overwrite for Draft logic
            all_reqs[existing_idx].update(req_data)
        else:
            all_reqs.append(req_data)
            
        save_data('requests.json', all_reqs)
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('dashboard'))
    
    timeline = load_config('timeline.json', {})
    return render_template('new_request.html', name=session['name'], role=session['role'], position=session.get('position',''), criteria=criteria, user=user_profile, edit_req=edit_req, fiscal_year=fiscal_year)

@app.route('/view_request/<req_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุภวัฒน์ ไกรษี (ตรวจสอบคำขอ)
def view_request(req_id):
    if 'username' not in session: return redirect(url_for('login'))
    all_reqs = load_data('requests.json')
    req_data = next((r for r in all_reqs if r['id'] == req_id), None)
    
    if not req_data:
        flash("ไม่พบข้อมูลคำขอ")
        return redirect(url_for('dashboard'))

    # Redirect drafts to edit page instead of view summary
    if req_data.get('status') == 'แบบร่าง' and session['role'] == 'applicant':
        return redirect(url_for('new_request', edit_id=req_id))
    
    # Calculate Remaining Days for Edit/Appeal
    edit_remaining = None
    appeal_remaining = None
    
    if req_data.get('status') == 'แก้ไข' and req_data.get('return_date'):
        edit_remaining = get_remaining_days(req_data['return_date'])
        
    if req_data.get('status') == 'ไม่อนุมัติ' and req_data.get('rejection_date'):
        appeal_remaining = get_remaining_days(req_data['rejection_date'])

    if request.method == 'POST':
        action = request.form.get('action')
        
        # Applicant Actions
        if req_data['status'] in ['แบบร่าง', 'แก้ไข'] and session['role'] == 'applicant':
            # Check for Edit Expiry if status is 'แก้ไข'
            if req_data['status'] == 'แก้ไข' and req_data.get('return_date'):
                rem = get_remaining_days(req_data['return_date'])
                if rem < 0:
                     flash("เกินกำหนดเวลาการแก้ไขคำขอ (7 วัน) ไม่สามารถบันทึกหรือส่งคำขอได้")
                     return redirect(url_for('view_request', req_id=req_id))

            req_data['title'] = request.form.get('title')
            req_data['category'] = request.form.get('category')
            req_data['evidence'] = request.form.get('evidence_link')
            req_data['status'] = "ส่งแล้ว" if action == "submit" else req_data['status']
            req_data['date'] = format_thai_date(datetime.now(), True)
            if action == "submit":
                create_notification(f"มีการแก้ไข/ส่งคำขอ {req_id} โดย {session['name']}", recipient_role='administration', req_id=req_id)
            save_data('requests.json', all_reqs)
            flash("อัปเดตข้อมูลเรียบร้อยแล้ว")
            return redirect(url_for('dashboard'))
            
        # Appeal Action (Applicant) - Single Form
        if action == 'submit_appeal' and session['role'] == 'applicant':
            appeal_reason = request.form.get('appeal_reason', '').strip()
            appeal_evidence = request.form.get('appeal_evidence', '').strip()
            
            if not appeal_reason:
                flash("กรุณาระบุเหตุผลในการอุทธรณ์")
                return redirect(url_for('view_request', req_id=req_id))

            appealed_count = 0
            for w in req_data['works']:
                if w.get('status') == 'ไม่อนุมัติ' and not w.get('already_appealed'):
                    w['status'] = 'รอการอุทธรณ์'
                    w['appeal_comment'] = appeal_reason
                    w['appeal_evidence'] = appeal_evidence
                    w['already_appealed'] = True
                    appealed_count += 1
            
            if appealed_count > 0:
                req_data['status'] = 'รอการอุทธรณ์'
                req_data['appeal_date'] = format_thai_date(datetime.now(), True)
                save_data('requests.json', all_reqs)
                create_notification(f"มีการยื่นอุทธรณ์คำขอ {req_id} ({appealed_count} รายการ)", recipient_role='committee', req_id=req_id)
                flash("ส่งคำอุทธรณ์เรียบร้อยแล้ว")
            else:
                flash("ไม่พบรายการที่สามารถยื่นอุทธรณ์ได้")
            
            return redirect(url_for('view_request', req_id=req_id))

        # Cancel Action (Applicant)
        if action == 'cancel' and session['role'] == 'applicant':
            allowed_to_cancel = ['แบบร่าง', 'ส่งแล้ว', 'แก้ไข', 'รอตรวจประวัติการยื่นขอ', 'ผลงานผ่าน', 'รอเสนอพิจารณา']
            if req_data.get('status') in allowed_to_cancel:
                req_data['status'] = 'ยกเลิก'
                req_data['cancel_date'] = format_thai_date(datetime.now(), True)
                save_data('requests.json', all_reqs)
                create_notification(f"คำขอ {req_id} ถูกยกเลิกโดยผู้ยื่น", recipient_role='administration', req_id=req_id)
                flash("ยกเลิกคำขอเรียบร้อยแล้ว")
                return redirect(url_for('dashboard'))
            else:
                flash("ไม่สามารถยกเลิกคำขอได้ในสถานะนี้")
                return redirect(url_for('view_request', req_id=req_id))

        # Legacy Individual Appeal (Keep for backward compatibility if needed, or remove)
        if action and action.startswith('appeal_work_') and session['role'] == 'applicant':
            try:
                work_idx = int(action.split('_')[-1])
                if work_idx < len(req_data['works']):
                    work = req_data['works'][work_idx]
                    
                    if work.get('already_appealed'):
                        flash("ไม่สามารถยื่นอุทธรณ์ได้มากกว่า 1 ครั้งสำหรับการดำเนินงานนี้")
                        return redirect(url_for('view_request', req_id=req_id))
                        
                    # Capture new fields
                    comment = request.form.get(f'appeal_comment_{work_idx}', '').strip()
                    if not comment:
                        flash("กรุณาระบุเหตุผลในการอุทธรณ์")
                        return redirect(url_for('view_request', req_id=req_id))
                    
                    work['appeal_comment'] = comment
                    work['appeal_evidence'] = request.form.get(f'appeal_evidence_{work_idx}')
                    work['status'] = 'รอการอุทธรณ์'
                    work['already_appealed'] = True
                    
                    # Also set the global status to trigger visibility in the Appeals panel
                    req_data['status'] = 'รอการอุทธรณ์'
                    req_data['appeal_date'] = format_thai_date(datetime.now(), True)
                    save_data('requests.json', all_reqs)
                    create_notification(f"มีการยื่นอุทธรณ์ผลงานในคำขอ {req_id}", recipient_role='committee', req_id=req_id)
                    flash(f"ยื่นอุทธรณ์ผลงานที่ {work_idx+1} เรียบร้อยแล้ว")
                    return redirect(url_for('view_request', req_id=req_id))
            except (ValueError, IndexError):
                pass

        # Appeal Decision (Committee) logic removed to use unified global buttons
        
        # Administration Actions
        elif session['role'] == 'administration' and req_data['status'] in ['ส่งแล้ว', 'ผลงานผ่าน', 'ผลงานซ้ำซ้อน', 'ซ้ำซ้อนบางส่วน', 'รอเสนอพิจารณา', 'อยู่ในรอบพิจารณา']:
            # ALWAYS Update Scores, Payments, and Total Amount if they are in the form
            new_sum = 0
            for i, work in enumerate(req_data['works']):
                # Update Score
                score_key = f"score_{i}"
                if score_key in request.form:
                    try:
                        work['score_calc'] = float(request.form.get(score_key))
                    except ValueError: pass
                
                # Update Individual Compensation
                comp_key = f"comp_{i}"
                if comp_key in request.form:
                    try:
                        val = float(request.form.get(comp_key))
                        # Force 0 if duplicate
                        if work.get('status') in ['ผลงานซ้ำซ้อน', 'ไม่อนุมัติ']:
                            val = 0
                        work['payment_calc'] = val
                    except ValueError: pass
                    
                if work.get('status') not in ['ผลงานซ้ำซ้อน', 'ไม่อนุมัติ']:
                    new_sum += work.get('score_calc', 0)
            
            req_data['score'] = new_sum
            
            # Recalculate Total Amount on Backend for integrity
            calculated_total_amount = sum(work.get('payment_calc', 0) for work in req_data['works'])
            
            # Update Total Amount (Prefer form value if provided, else use calculated)
            if request.form.get('amount'):
                try:
                    req_data['approved_amount'] = float(request.form.get('amount'))
                except ValueError:
                    req_data['approved_amount'] = calculated_total_amount
            else:
                req_data['approved_amount'] = calculated_total_amount

            # Handle Actions
            if action == 'return':
                comment = request.form.get('comment', '').strip()
                if not comment:
                    flash("กรุณาระบุสิ่งที่ต้องแก้ไข ก่อนทำการส่งคืน")
                    return redirect(url_for('view_request', req_id=req_id))
                    
                req_data['status'] = 'แก้ไข'
                req_data['comment'] = comment
                req_data['return_date'] = format_thai_date(datetime.now())
                create_notification(f"คำขอ {req_id} ถูกส่งคืนแก้ไข: {comment}", recipient_username=req_data['applicant'], req_id=req_id)
                save_data('requests.json', all_reqs)
                flash("ส่งคืนคำขอให้ผู้ยื่นแก้ไขแล้ว")
                return redirect(url_for('dashboard'))

            elif action == 'pass':
                req_data['status'] = 'รอตรวจประวัติการยื่นขอ'
                save_data('requests.json', all_reqs)
                flash("ส่งต่อให้งานวิจัยเรียบร้อยแล้ว")
                create_notification(f"คำขอ {req_id} รอตรวจประวัติการยื่นขอ", recipient_role='research', req_id=req_id)
                return redirect(url_for('dashboard'))

            elif action == 'mark_ready':
                req_data['status'] = 'รอเสนอพิจารณา'
                save_data('requests.json', all_reqs)
                flash("บันทึกข้อมูลและเตรียมเสนอเข้าที่ประชุมเรียบร้อยแล้ว")
                return redirect(url_for('dashboard'))

            elif action == 'reject':
                comment = request.form.get('comment', '').strip()
                req_data['status'] = 'ไม่อนุมัติ'
                req_data['comment'] = comment
                req_data['rejection_date'] = format_thai_date(datetime.now())
                create_notification(f"คำขอ {req_id} ไม่อนุมัติการอนุมัติ", recipient_username=req_data['applicant'], req_id=req_id)
                save_data('requests.json', all_reqs)
                flash("ปฏิเสธคำขอเรียบร้อยแล้ว")
                return redirect(url_for('dashboard'))

            # If it was just a manual save or fallthrough
            save_data('requests.json', all_reqs)
            flash("บันทึกข้อมูลเรียบร้อยแล้ว")
            return redirect(url_for('view_request', req_id=req_id))

        # Research Actions
        elif req_data['status'] == 'รอตรวจประวัติการยื่นขอ' and session['role'] == 'research':
            if action == 'research_bulk_verify':
                selected_indices = request.form.getlist('selected_works')
                for idx_str in selected_indices:
                    try:
                        idx = int(idx_str)
                        if idx < len(req_data['works']):
                            req_data['works'][idx]['status'] = 'ผลงานผ่าน'
                    except: pass
                flash(f"ยืนยัน 'ไม่เคยใช้' ให้กับ {len(selected_indices)} รายการ")
            elif action == 'research_bulk_duplicate':
                selected_indices = request.form.getlist('selected_works')
                for idx_str in selected_indices:
                    try:
                        idx = int(idx_str)
                        if idx < len(req_data['works']):
                            req_data['works'][idx]['status'] = 'ผลงานซ้ำซ้อน'
                    except: pass
                flash(f"ระบุ 'เคยใช้แล้ว' ให้กับ {len(selected_indices)} รายการ")
            elif action and action.startswith('verify_work_'):
                idx = int(action.split('_')[-1])
                if idx < len(req_data['works']):
                    req_data['works'][idx]['status'] = 'ผลงานผ่าน'
                    flash(f"ยืนยันความถูกต้องผลงานที่ {idx+1} เรียบร้อยแล้ว")
            elif action and action.startswith('duplicate_work_'):
                idx = int(action.split('_')[-1])
                if idx < len(req_data['works']):
                    req_data['works'][idx]['status'] = 'ผลงานซ้ำซ้อน'
                    flash(f"ระบุงานซ้ำซ้อนสำหรับผลงานที่ {idx+1}")
            elif action == 'finalize_research':
                # Check if all works have been reviewed
                all_reviewed = all(w.get('status') in ['ผลงานผ่าน', 'ผลงานซ้ำซ้อน'] for w in req_data['works'])
                if not all_reviewed:
                    flash("กรุณาตรวจสอบผลงานให้ครบทุกรายการก่อนส่งผล")
                    return redirect(url_for('view_request', req_id=req_id))
                
                # Determine overall status
                any_duplicate = any(w.get('status') == 'ผลงานซ้ำซ้อน' for w in req_data['works'])
                any_pass = any(w.get('status') == 'ผลงานผ่าน' for w in req_data['works'])
                
                if any_duplicate and any_pass:
                    req_data['status'] = 'ซ้ำซ้อนบางส่วน'
                    create_notification(f"พบงานซ้ำซ้อนบางส่วนในคำขอ {req_id}", recipient_role='administration', req_id=req_id)
                elif any_duplicate:
                    req_data['status'] = 'ผลงานซ้ำซ้อน'
                    create_notification(f"พบงานซ้ำซ้อนทั้งหมดในคำขอ {req_id}", recipient_role='administration', req_id=req_id)
                else:
                    req_data['status'] = 'ผลงานผ่าน'
                    create_notification(f"ตรวจสอบผลงานคำขอ {req_id} เรียบร้อยแล้ว (ถูกต้องทั้งหมด)", recipient_role='administration', req_id=req_id)
                
                # Recalculate based on new research findings (duplicate works)
                new_score, new_comp = calculate_compensation(
                    req_data['works'], 
                    req_data.get('applicant_info', {}).get('academic_position', ''), 
                    req_data.get('fiscal_year')
                )
                req_data['score'] = new_score
                req_data['suggested_compensation'] = new_comp
                # Also update total fields used by display components
                req_data['total_score'] = new_score
                req_data['total_compensation'] = new_comp
                req_data['approved_amount'] = new_comp
                
                save_data('requests.json', all_reqs)
                flash("ส่งผลการตรวจสอบไปยังงานบุคคลเรียบร้อยแล้ว")
                return redirect(url_for('dashboard'))
                
            save_data('requests.json', all_reqs)
            return redirect(url_for('view_request', req_id=req_id))

        # Committee Actions
        elif req_data['status'] in ['รอการพิจารณา', 'รอการอุทธรณ์'] and session['role'] == 'committee':
            original_status = req_data['status']
            comment = request.form.get('comment', '').strip()

            if action == 'approve':
                req_data['status'] = 'อนุมัติ'
                if original_status == 'รอการอุทธรณ์':
                     if 'appeal' not in req_data: req_data['appeal'] = {}
                     req_data['appeal']['status'] = 'อนุมัติ'
                
                # Update individual works undergoing appeal
                for w in req_data['works']:
                    if w.get('status') == 'รอการอุทธรณ์':
                        w['status'] = 'อนุมัติ'
                        w['comment'] = "ผ่านการอุทธรณ์"

                # Recalculate based on newly approved items
                new_score, new_comp = calculate_compensation(
                    req_data['works'], 
                    req_data.get('applicant_info', {}).get('academic_position', ''), 
                    req_data.get('fiscal_year')
                )
                req_data['score'] = new_score
                req_data['approved_amount'] = new_comp
                
                flash("อนุมัติคำขอและผลการอุทธรณ์เรียบร้อยแล้ว")
                create_notification(f"คำขอ {req_id} ได้รับการอนุมัติแล้ว", recipient_username=req_data['applicant'], req_id=req_id)
            
            elif action == 'reject':
                req_data['status'] = 'ไม่อนุมัติ'
                req_data['comment'] = comment
                req_data['rejection_date'] = format_thai_date(datetime.now())
                
                if original_status == 'รอการอุทธรณ์':
                     if 'appeal' not in req_data: req_data['appeal'] = {}
                     req_data['appeal']['status'] = 'ไม่อนุมัติ'
                
                # Update individual works undergoing appeal
                for w in req_data['works']:
                    if w.get('status') == 'รอการอุทธรณ์':
                        w['status'] = 'ไม่อนุมัติ'
                        w['comment'] = comment or "ไม่อนุมัติ"

                # Recalculate (score will drop)
                new_score, new_comp = calculate_compensation(
                    req_data['works'], 
                    req_data.get('applicant_info', {}).get('academic_position', ''), 
                    req_data.get('fiscal_year')
                )
                req_data['score'] = new_score
                req_data['approved_amount'] = new_comp

                flash("ไม่อนุมัติคำขอรวม")
                create_notification(f"คำขอ {req_id} ถูกปฏิเสธ (ไม่อนุมัติ)", recipient_username=req_data['applicant'], req_id=req_id)
            
            save_data('requests.json', all_reqs)
            return redirect(url_for('dashboard'))

    # Fetch applicant history for duplicate checking
    applicant_history = [r for r in all_reqs if r['applicant'] == req_data['applicant'] and r['id'] != req_id]
    
    # Load criteria for calc
    all_criteria = load_config('criteria.json', [])
    criteria = next((c for c in all_criteria if str(c.get('fiscal_year')) == str(req_data.get('fiscal_year'))), {})

    return render_template('view_request.html', name=session['name'], role=session['role'], position=session.get('position',''), req=req_data, history=applicant_history, edit_remaining=edit_remaining, appeal_remaining=appeal_remaining, criteria=criteria)

@app.route('/appeal/<req_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นางสาวเบญจมาศ จ่านันท์ (ยื่นอุทธรณ์)
def appeal_request(req_id):
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('login'))
    all_reqs = load_data('requests.json')
    req_data = next((r for r in all_reqs if r['id'] == req_id), None)
    
    if not req_data or req_data['status'] != 'ไม่อนุมัติ':
        flash("ไม่สามารถยื่นอุทธรณ์ได้สำหรับคำขอนี้")
        return redirect(url_for('view_request', req_id=req_id))

    if req_data.get('appeal'):
        flash("คุณได้ยื่นอุทธรณ์สำหรับคำขอนี้ไปแล้ว")
        return redirect(url_for('view_request', req_id=req_id))
        
    # Check 7 Days Limit
    appeal_remaining = None
    if 'rejection_date' in req_data:
        appeal_remaining = get_remaining_days(req_data['rejection_date'])
        if appeal_remaining < 0:
             flash("เกินกำหนดเวลาการยื่นอุทธรณ์ (7 วัน)")
             return redirect(url_for('view_request', req_id=req_id))

    if request.method == 'POST':
        req_data['status'] = 'รอการอุทธรณ์'
        req_data['appeal'] = {
            "reason": request.form.get('reason'),
            "evidence": request.form.get('evidence_link'),
            "date": format_thai_date(datetime.now(), True),
            "status": "รอพิจารณา"
        }
        create_notification(f"มีการยื่นอุทธรณ์สำหรับคำขอ {req_id}", recipient_role='committee', req_id=req_id)
        save_data('requests.json', all_reqs)
        flash("ยื่นอุทธรณ์เรียบร้อยแล้ว")
        return redirect(url_for('view_request', req_id=req_id))

    return render_template('appeal_request.html', name=session['name'], role=session['role'], position=session.get('position',''), req=req_data, appeal_remaining=appeal_remaining)


@app.route('/logout') # ผู้รับผิดชอบ: นาย ธนวรรธ ทองตื้อ (ออกจากระบบ)
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/manage_criteria') # ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ (Admin/เกณฑ์)
def manage_criteria():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    timeline = load_config('timeline.json', {})
    criteria = load_config('criteria.json', [])
    if criteria is None: criteria = []
    if isinstance(criteria, dict): criteria = []
    
    # Sort for display
    if isinstance(criteria, list):
        criteria.sort(key=lambda x: str(x.get('fiscal_year', '')), reverse=True)
        
    return render_template('manage_criteria.html', criteria=criteria, name=session['name'], role=session['role'], timeline=timeline)

@app.route('/manage/timeline', methods=['GET']) # ผู้รับผิดชอบ: นายฐิติวัฒน์ กุลบุตร (กำหนดการ)
def manage_timeline():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    timelines = load_config('timeline.json', [])
    if isinstance(timelines, dict): timelines = []
    
    timelines.sort(key=lambda x: str(x.get('fiscal_year', '')), reverse=True)
        
    return render_template('manage_timeline.html', name=session['name'], role=session['role'], timelines=timelines, position=session.get('position',''))

@app.route('/edit_timeline', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายฐิติวัฒน์ กุลบุตร (กำหนดการ)
def edit_timeline():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    timelines = load_config('timeline.json', [])
    if isinstance(timelines, dict): timelines = []
    
    fiscal_year = request.args.get('year')
    timeline_data = next((t for t in timelines if str(t.get('fiscal_year')) == str(fiscal_year)), None)
    
    if request.method == 'POST':
        action = request.form.get('action')
        new_year = request.form.get('fiscal_year')
        
        if action == 'delete':
            timelines = [t for t in timelines if str(t.get('fiscal_year')) != str(fiscal_year)]
            save_data('timeline.json', timelines)
            flash(f"ลบข้อมูลปีงบประมาณ {fiscal_year} เรียบร้อยแล้ว")
            return redirect(url_for('manage_timeline'))
            
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        new_entry = {
            "fiscal_year": new_year,
            "start_date": start_date,
            "end_date": end_date
        }
        
        existing_idx = next((i for i, t in enumerate(timelines) if str(t.get('fiscal_year')) == str(new_year)), -1)
        if existing_idx > -1:
            timelines[existing_idx] = new_entry
        else:
            timelines.append(new_entry)
            
        save_data('timeline.json', timelines)
        flash(f"บันทึกข้อมูลปีงบประมาณ {new_year} เรียบร้อยแล้ว")
        return redirect(url_for('manage_timeline'))

    return render_template('edit_timeline.html', name=session['name'], role=session['role'], timeline=timeline_data, year=fiscal_year)

@app.route('/edit_criteria', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ (เกณฑ์คะแนน)
def edit_criteria():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    criteria_list = load_config('criteria.json', [])
    if criteria_list is None: criteria_list = []
    if isinstance(criteria_list, dict): criteria_list = []

    fiscal_year = request.args.get('year')
    
    # Find existing or initialize new
    criteria_data = next((c for c in criteria_list if str(c.get('fiscal_year')) == str(fiscal_year)), None)
    
    if request.method == 'POST':
        action = request.form.get('action')
        new_year = request.form.get('fiscal_year')
        
        if action == 'delete':
             if criteria_data:
                criteria_list = [c for c in criteria_list if str(c.get('fiscal_year')) != str(fiscal_year)]
                save_data('criteria.json', criteria_list)
                flash(f"ลบข้อมูลปีงบประมาณ {fiscal_year} เรียบร้อยแล้ว")
             return redirect(url_for('manage_criteria'))
        
        # Helper to strict float
        def to_float(val):
            try: return float(val)
            except: return 0.0

        # Helper to get tiered rules from form
        def get_tiers(pos_key):
            tiers = []
            for i in range(2): # Only 2 tiers as requested
                min_s = request.form.get(f'{pos_key}_min_{i}')
                amt = request.form.get(f'{pos_key}_amt_{i}')
                if min_s is not None and amt is not None and min_s.strip() != "":
                    tiers.append({"min_score": to_float(min_s), "amount": to_float(amt)})
            return tiers

        new_data = {
            "fiscal_year": new_year,
            "quality_scores": {
                "research": {
                    "tier1": to_float(request.form.get('research_tier1')),
                    "non_q": to_float(request.form.get('research_non_q')),
                    "national": to_float(request.form.get('research_national'))
                },
                "merged_abc": {
                    "a_plus": to_float(request.form.get('merged_ap')),
                    "a": to_float(request.form.get('merged_a')),
                    "b": to_float(request.form.get('merged_b'))
                },
                "textbook": {
                    "publisher": to_float(request.form.get('textbook_pub')),
                    "general": to_float(request.form.get('textbook_gen'))
                },
                "creative": {
                    "international": to_float(request.form.get('creative_inter')),
                    "cooperation": to_float(request.form.get('creative_coop')),
                    "national": to_float(request.form.get('creative_nat'))
                },
                "other": {"creative": to_float(request.form.get('creative'))} # Legacy compatibility
            },
            "role_weights": {
                "main": to_float(request.form.get('role_main')),
                "co": to_float(request.form.get('role_co'))
            },
            "payment_rules": {
                "asst_prof": get_tiers('asst'),
                "assoc_prof": get_tiers('assoc'),
                "prof": get_tiers('prof')
            }
        }
        
        # If updating, remove old entry first
        criteria_list = [c for c in criteria_list if str(c.get('fiscal_year')) != str(fiscal_year)]
        criteria_list.append(new_data)
        
        save_data('criteria.json', criteria_list)
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('manage_criteria'))

    if not criteria_data:
        # Default Template for new criteria
        criteria_data = {
            "fiscal_year": "",
            "quality_scores": {
                "research": {"tier1": 1.25, "non_q": 1.00, "national": 0.75},
                "merged_abc": {"a_plus": 1.25, "a": 1.00, "b": 0.75},
                "textbook": {"publisher": 1.25, "general": 1.00},
                "creative": {"international": 1.25, "cooperation": 1.00, "national": 0.75},
                "other": {"creative": 1.00}
            },
            "role_weights": {"main": 1.0, "co": 0.5},
            "payment_rules": {
                "asst_prof": [{"min_score": 0.50, "amount": 3000}, {"min_score": 0.75, "amount": 5600}],
                "assoc_prof": [{"min_score": 0.75, "amount": 6000}, {"min_score": 1.25, "amount": 9900}],
                "prof": [{"min_score": 1.25, "amount": 9000}, {"min_score": 1.50, "amount": 13000}]
            }
        }

    return render_template('edit_criteria.html', data=criteria_data, name=session['name'], role=session['role'])





@app.route('/uploads/<req_id>/<work_id>/<filename>') # ผู้รับผิดชอบ: นาย ธนวรรธ ทองตื้อ (อัปโหลดไฟล์)
def uploaded_file(req_id, work_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], req_id, work_id), filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)