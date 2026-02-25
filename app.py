"""
app.py
จุดเริ่มต้นของแอปพลิเคชัน (Entry Point)
- สร้าง Flask app
- ตั้งค่าระบบ
- ลงทะเบียน Blueprint ทั้งหมด
- ลงทะเบียน context processors และ template filters
"""

from flask import Flask, session
from database import init_db, query_db
import os

# ──────────────────────────────────────────────
# สร้าง Flask App
# ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "academic_secret_key"

# Initialize database
init_db()

# ──────────────────────────────────────────────
# ตั้งค่า Upload Folder
# ──────────────────────────────────────────────
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'zip', 'rar'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ──────────────────────────────────────────────
# ลงทะเบียน Blueprints
# ──────────────────────────────────────────────
from routes import auth_bp, main_bp, requests_bp, rounds_bp, admin_bp, api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(requests_bp)
app.register_blueprint(rounds_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# ──────────────────────────────────────────────
# Context Processor (ตัวแปรที่ใช้ร่วมกันทุก template)
# ──────────────────────────────────────────────
from datetime import datetime
from utils import is_within_timeline, get_current_fiscal_year, parse_thai_date, format_thai_date

@app.context_processor
def inject_timeline():
    can_submit = is_within_timeline()
    current_fy = str(get_current_fiscal_year())
    
    # Fetch config from DB (Try current, fallback to latest)
    config = query_db('SELECT * FROM FiscalYearConfig WHERE fiscal_year = ?', (current_fy,), one=True)
    if not config:
        config = query_db('SELECT * FROM FiscalYearConfig ORDER BY fiscal_year DESC LIMIT 1', one=True)
    
    timeline_msg = ""
    now = datetime.now()
    
    # Simple message if system is closed based on global range
    if not can_submit:
        start_date = config['start_date'] if config else '01/10'
        timeline_msg = f"ขออภัย! ขณะนี้ระบบปิดการรับคำขอ\nจะเปิดรับคำขออีกครั้งในวันที่ {start_date} ของรอบปีงบประมาณถัดไป"
        
    has_submitted = False
    if 'username' in session and session['role'] == 'applicant':
        # Check from DB instead of JSON
        user_req = query_db('SELECT * FROM RequestRecord WHERE applicant_username = ? AND fiscal_year = ? AND status != ?', 
                           (session['username'], current_fy, 'แบบร่าง'), one=True)
        if user_req:
            has_submitted = True
            
    return dict(can_submit=can_submit, timeline=config, timeline_message=timeline_msg, has_submitted_this_year=has_submitted)

# ──────────────────────────────────────────────
# Template Filters
# ──────────────────────────────────────────────

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
    from utils import load_data
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
    if initial_type in mapping:
        return mapping[initial_type]
    
    # Try to load from work_types.json if not in mapping
    work_types = load_data('work_types.json')
    wt = next((t for t in work_types if t['id'] == initial_type), None)
    if wt:
        return wt.get('label', initial_type)
        
    return initial_type


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


# ──────────────────────────────────────────────
# Run App
# ──────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, port=5000)