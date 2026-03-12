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
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# ──────────────────────────────────────────────
# Context Processor (ตัวแปรที่ใช้ร่วมกันทุก template)
# ──────────────────────────────────────────────
from datetime import datetime
from utils import is_within_timeline, get_current_fiscal_year, parse_thai_date, format_thai_date

@app.context_processor
def inject_timeline():
    is_open, active_reason, next_open = is_within_timeline()
    current_fy = str(get_current_fiscal_year())
    
    config_row = query_db('SELECT * FROM TimelineConfig WHERE fiscal_year = ?', (current_fy,), one=True)
    if not config_row:
        config_row = query_db('SELECT * FROM TimelineConfig ORDER BY fiscal_year DESC LIMIT 1', one=True)
    
    config = dict(config_row) if config_row else None
    if config and config.get('rounds_json'):
        config['rounds'] = json.loads(config['rounds_json'])
    
    timeline_msg = ""
    if not is_open:
        if active_reason and active_reason not in ["ไม่อยู่ในช่วงเวลาการเปิดรับคำขอ", "ยังไมาเปิดรับคำขอใหม่"]:
            timeline_msg = f"ขณะนี้อยู่ในช่วง {active_reason} (จึงปิดการรับคำขอใหม่)"
        else:
            timeline_msg = f"ขณะนี้หมดเวลาเปิดรับคำขอใหม่ (ท่านยังสามารถยื่นคำขอที่ถูกส่งกลับมาแก้ไขได้)"
        
        if next_open:
            timeline_msg += f"\nจะเปิดให้ยื่นได้อีกครั้งในวันที่ {next_open}"
        
    has_submitted = False
    if 'username' in session and session['role'] == 'applicant':
        user_req = query_db('SELECT * FROM RequestRecord WHERE applicant_username = ? AND fiscal_year = ? AND status != ?', 
                           (session['username'], current_fy, 'แบบร่าง'), one=True)
        if user_req:
            has_submitted = True
            
    if has_submitted:
        timeline_msg = "คุณได้ยื่นคำขอสำหรับปีงบประมาณนี้เรียบร้อยแล้ว"

    return dict(can_submit=is_open, timeline=config, timeline_message=timeline_msg, has_submitted_this_year=has_submitted)

# ──────────────────────────────────────────────
# Template Filters
# ──────────────────────────────────────────────

@app.template_filter('role_status_label')
def role_status_label(status, role):
    labels = {
        'administration': {
            'ส่งแล้ว': 'รอตรวจสอบ', 'แก้ไข': 'ส่งคืนแก้ไขแล้ว', 'รอตรวจประวัติการยื่นขอ': 'ส่งให้งานวิจัยแล้ว',
            'ผลงานผ่าน': 'ผ่านการตรวจสอบประวัติ', 'ผลงานซ้ำซ้อน': 'ผลงานเคยถูกใช้แล้ว', 'ซ้ำซ้อนบางส่วน': 'ซ้ำซ้อนบางส่วน',
            'รอการพิจารณา': 'รอการพิจารณา'
        },
        'research': {
            'รอตรวจประวัติการยื่นขอ': 'รอตรวจสอบ', 'ผลงานผ่าน': 'ผ่านการตรวจสอบประวัติ', 
            'ผลงานซ้ำซ้อน': 'เคยใช้แล้ว', 'ซ้ำซ้อนบางส่วน': 'ซ้ำซ้อนบางส่วน'
        },
        'committee': {
            'รอการพิจารณา': 'รอการพิจารณา', 'รอการอุทธรณ์': 'รอพิจารณาอุทธรณ์'
        },
        'applicant': {
            'ส่งแล้ว': 'ส่งแล้ว', 'รอตรวจประวัติการยื่นขอ': 'กำลังตรวจสอบคำขอ', 
            'ผลงานผ่าน': 'ผ่านการตรวจสอบประวัติ', 'ผลงานซ้ำซ้อน': 'ผลงานเคยถูกใช้แล้ว',
            'ซ้ำซ้อนบางส่วน': 'ซ้ำซ้อนบางส่วน', 'รอการพิจารณา': 'รอการพิจารณา'
        }
    }
    return labels.get(role, {}).get(status, 'ยกเลิก' if status == 'ยกเลิก' else status)


@app.template_filter('rich_status_label')
def rich_status_label(req, role):
    status = req.get('status', '')
    works = req.get('works', [])
    
    # Check if this is an approved request that came from an appeal
    is_appeal_success = status == 'อนุมัติ' and any(w.get('already_appealed') for w in works)
    
    if is_appeal_success:
        return 'อนุมัติ (อุทธรณ์สำเร็จ)'
    
    if status == 'อนุมัติ' and any(w.get('status') in ['ไม่อนุมัติ', 'ผลงานซ้ำซ้อน'] for w in works):
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
# Error Handlers
# ──────────────────────────────────────────────
@app.errorhandler(413)
def request_entity_too_large(error):
    max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return f'''
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <title>ขนาดไฟล์เกินกำหนด</title>
        <style>
            body {{ font-family: 'Sarabun', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f4f6f9; margin: 0; }}
            .card {{ background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; max-width: 500px; width: 90%; }}
            h1 {{ color: #e74c3c; margin-top: 0; }}
            p {{ color: #555; font-size: 16px; margin: 15px 0; line-height: 1.5; }}
            .size-badge {{ display: inline-block; background-color: #fef0f0; color: #e74c3c; padding: 8px 15px; border-radius: 20px; font-weight: bold; margin: 15px 0; }}
            .btn {{ display: inline-block; margin-top: 20px; padding: 10px 25px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; transition: background 0.3s; }}
            .btn:hover {{ background: #2980b9; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>ไฟล์มีขนาดใหญ่เกินไป</h1>
            <p>ขออภัย ข้อมูลหรือไฟล์ที่คุณพยายามอัปโหลดมีขนาดรวมกันเกินกว่าที่ระบบสามารถรับได้</p>
            <div class="size-badge">ระบบรองรับขนาดสูงสุด: {max_mb} MB</div>
            <p>กรุณาลดขนาดไฟล์ (เช่น การบีบอัด PDF) หรือแบ่งไฟล์ แล้วลองทำรายการใหม่อีกครั้ง</p>
            <a href="javascript:history.back()" class="btn">ย้อนกลับไปแก้ไข</a>
        </div>
    </body>
    </html>
    ''', 413

# ──────────────────────────────────────────────
# Run App
# ──────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, port=5001)