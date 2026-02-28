"""
app.py
จุดเริ่มต้นของแอปพลิเคชัน (Entry Point)
- สร้าง Flask app
- ตั้งค่าระบบ
- ลงทะเบียน Blueprint ทั้งหมด
- ลงทะเบียน context processors และ template filters
"""

from flask import Flask, session, redirect, url_for
from database import init_db, query_db
import os
import json

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
from routes import auth_bp, main_bp, requests_bp, admin_bp, api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(requests_bp)
# app.register_blueprint(rounds_bp) # Remove Batching
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
    config_row = query_db('SELECT * FROM TimelineConfig WHERE fiscal_year = ?', (current_fy,), one=True)
    if not config_row:
        config_row = query_db('SELECT * FROM TimelineConfig ORDER BY fiscal_year DESC LIMIT 1', one=True)
    
    config = dict(config_row) if config_row else None
    if config and config.get('rounds_json'):
        config['rounds'] = json.loads(config['rounds_json'])
    
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
    labels = {
        'administration': {
            'ส่งแล้ว': 'รอตรวจสอบ', 'แก้ไข': 'ส่งคืนแก้ไขแล้ว', 'รอตรวจประวัติการยื่นขอ': 'ส่งให้งานวิจัยแล้ว',
            'ผลงานผ่าน': 'รอคำนวนค่าตอบแทน', 'ผลงานซ้ำซ้อน': 'ผลงานเคยถูกใช้แล้ว', 'ซ้ำซ้อนบางส่วน': 'ซ้ำซ้อนบางส่วน',
            'รอการพิจารณา': 'รอการพิจารณา'
        },
        'research': {
            'รอตรวจประวัติการยื่นขอ': 'รอตรวจสอบ', 'ผลงานผ่าน': 'ไม่เคยใช้', 
            'ผลงานซ้ำซ้อน': 'เคยใช้แล้ว', 'ซ้ำซ้อนบางส่วน': 'ซ้ำซ้อนบางส่วน'
        },
        'committee': {
            'รอการพิจารณา': 'รอการพิจารณา', 'รอการอุทธรณ์': 'รอพิจารณาอุทธรณ์'
        },
        'applicant': {
            'ส่งแล้ว': 'ส่งแล้ว', 'รอตรวจประวัติการยื่นขอ': 'กำลังตรวจสอบคำขอ', 
            'ผลงานผ่าน': 'ผ่าน (รอเจ้าหน้าที่งานบุคคลส่งพิจารณา)', 'ผลงานซ้ำซ้อน': 'ผลงานเคยถูกใช้แล้ว',
            'ซ้ำซ้อนบางส่วน': 'ซ้ำซ้อนบางส่วน', 'รอการพิจารณา': 'รอการพิจารณา'
        }
    }
    return labels.get(role, {}).get(status, 'ยกเลิก' if status == 'ยกเลิก' else status)


@app.template_filter('rich_status_label')
def rich_status_label(req, role):
    status = req.get('status', '')
    if status == 'อนุมัติ' and any(w.get('status') in ['ไม่อนุมัติ', 'ผลงานซ้ำซ้อน'] for w in req.get('works', [])):
        return 'อนุมัติ (ไม่อนุญาตบางส่วน)'
    return role_status_label(status, role)


@app.template_filter('translate_work_type')
def translate_work_type(initial_type):
    mapping = {
        'research': 'บทความงานวิจัย', 'textbook': 'ตำราหรือหนังสือ', 'creative': 'งานสร้างสรรค์',
        'social': 'ผลงานรับใช้ท้องถิ่นและสังคม', 'industry': 'ผลงานวิชาการเพื่ออุตสาหกรรม',
        'teaching': 'ผลงานการสอน', 'policy': 'ผลงานวิชาการเพื่อพัฒนานโยบายสาธารณะ', 'innovation': 'ผลงานนวัตกรรม'
    }
    if initial_type in mapping: return mapping[initial_type]
    
    # Check DB
    wt = query_db('SELECT * FROM WorkType WHERE id = ?', (initial_type,), one=True)
    return wt['label'] if wt else initial_type


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
    app.run(debug=True, port=5001)