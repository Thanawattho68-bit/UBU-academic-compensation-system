"""
routes/api.py
จัดการ API routes และการให้บริการไฟล์ที่อัปโหลด
ผู้รับผิดชอบ:
  - นายกฤษดา ตะเคียนเกลี้ยง 68114540065 (ตรวจสอบความซ้ำซ้อน)
  - นายธนวรรธ ทองตื้อ 68114540258 (เพิ่ม/ลบประเภทผลงาน, อัปโหลดไฟล์)
"""

import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, session, send_from_directory, current_app
from werkzeug.utils import secure_filename
from database import query_db, execute_db
from utils import parse_thai_date, deserialize_request, calculate_compensation

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/check_work_duplicate', methods=['POST']) # ผู้รับผิดชอบ: นายกฤษดา ตะเคียนเกลี้ยง 68114540065 (ตรวจสอบความซ้ำซ้อน)
def api_check_work_duplicate():
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    date_publish_str = data.get('date_publish', '')
    req_id = data.get('req_id', '')

    if not title:
        return jsonify({"success": False, "message": "กรุณาระบุชื่อผลงาน"})

    all_rows = query_db('SELECT * FROM RequestRecord')
    all_reqs = [deserialize_request(r) for r in all_rows]
    
    self_duplicates = []
    shared_works = []
    
    current_req = next((r for r in all_reqs if r['id'] == req_id), None)
    current_username = current_req['applicant_username'] if current_req else session['username']

    for r in all_reqs:
        if r['id'] == req_id:
            continue
        
        for w in r.get('works', []):
            w_title = w.get('details', {}).get('title', '').strip()
            if w_title.lower() == title.lower():
                item = {
                    "id": r['id'],
                    "applicant": r.get('applicant_name', r['applicant']),
                    "status": r['status'],
                    "fiscal_year": r.get('fiscal_year', '-')
                }
                if r['applicant_username'] == current_username:
                    self_duplicates.append(item)
                else:
                    shared_works.append(item)

    # Check Age (2 years limit)
    is_old = False
    age_years = 0
    checked_date = False
    
    if date_publish_str:
        dt_pub = parse_thai_date(date_publish_str)
        if dt_pub:
            checked_date = True
            now = datetime.now()
            age_years = now.year - dt_pub.year
            if age_years > 2:
                is_old = True
            elif age_years == 2:
                if now.month < dt_pub.month or (now.month == dt_pub.month and now.day < dt_pub.day):
                    pass
                else:
                    is_old = True

    return jsonify({
        "success": True,
        "is_duplicate": len(self_duplicates) > 0,
        "self_duplicate_details": self_duplicates,
        "shared_details": shared_works,
        "is_old": is_old,
        "age_years": age_years,
        "checked_date": checked_date
    })


@api_bp.route('/api/add_work_type', methods=['POST']) # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ 68114540258 (เพิ่มประเภทผลงาน)
def api_add_work_type():
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "ไม่มีสิทธิ์ดำเนินการ"}), 403

    data = request.get_json(silent=True) or {}
    label = data.get('label', '').strip()
    if not label:
        return jsonify({"success": False, "message": "กรุณาระบุชื่อประเภทผลงาน"})
    
    # Check for duplicate label in DB
    existing = query_db('SELECT * FROM WorkType WHERE label = ?', (label,), one=True)
    if existing:
        return jsonify({"success": False, "message": "ประเภทผลงานนี้มีอยู่แล้วในระบบ"})
    
    # Generate unique ID
    new_id = f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    execute_db('INSERT INTO WorkType (id, label, is_custom) VALUES (?, ?, ?)', (new_id, label, 1))
    
    return jsonify({"success": True, "type": {"id": new_id, "label": label, "is_custom": True}})


@api_bp.route('/api/delete_work_type', methods=['POST']) # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ 68114540258 (ลบประเภทผลงาน)
def api_delete_work_type():
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "ไม่มีสิทธิ์ดำเนินการ"}), 403

    data = request.get_json(silent=True) or {}
    type_id = data.get('id', '')
    
    target = query_db('SELECT * FROM WorkType WHERE id = ?', (type_id,), one=True)
    
    if not target:
        return jsonify({"success": False, "message": "ไม่พบประเภทผลงานที่ต้องการลบ"})
    
    if not target['is_custom']:
        return jsonify({"success": False, "message": "ไม่สามารถลบประเภทผลงานหลักของระบบได้"})
    
    execute_db('DELETE FROM WorkType WHERE id = ?', (type_id,))
    
    return jsonify({"success": True})


@api_bp.route('/uploads/<req_id>/<work_id>/<filename>') # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ 68114540258 (อัปโหลดไฟล์)
def uploaded_file(req_id, work_id, filename):
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    # เชื่อมต่อกับ database.db เพื่อตรวจสอบข้อมูลคำขอและสิทธิ์การเข้าถึง
    req = query_db('SELECT * FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    if not req:
        return jsonify({"success": False, "message": "ไม่พบข้อมูลคำขอในฐานข้อมูล"}), 404
        
    role = session['role']
    username = session['username']
    
    # ตรวจสอบสิทธิ์: ถ้าเป็นผู้สมัคร ต้องดูได้เฉพาะของตัวเอง (ผู้ดูแลและกรรมการดูได้หมด)
    if role == 'applicant' and req['applicant_username'] != username:
        return jsonify({"success": False, "message": "คุณไม่มีสิทธิ์เข้าถึงไฟล์นี้"}), 403
        
    safe_req_id = secure_filename(req_id)
    safe_work_id = secure_filename(work_id)
    safe_filename = secure_filename(filename)
    if not safe_filename or safe_filename != filename:
        return jsonify({"success": False, "message": "ชื่อไฟล์ไม่ถูกต้อง"}), 400
    # ป้องกัน path traversal
    for part in (req_id, work_id, filename):
        if not part or '..' in part or '/' in part or '\\' in part:
            return jsonify({"success": False, "message": "พาธไม่ถูกต้อง"}), 400
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], req_id, work_id), filename)


@api_bp.route('/api/estimate_compensation', methods=['POST'])
def api_estimate_compensation():
    """API endpoint สำหรับคำนวณคะแนนและค่าตอบแทน ใช้ logic เดียวกับ Backend"""
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    data = request.get_json(silent=True) or {}
    works = data.get('works', [])
    position = data.get('position', '')
    fiscal_year = data.get('fiscal_year', '')
    
    score, comp = calculate_compensation(works, position, fiscal_year)
    
    # Return per-work breakdown too
    works_detail = []
    for w in works:
        works_detail.append({
            'base_score': w.get('base_score', 0),
            'weight': w.get('weight', 0),
            'score_calc': w.get('score_calc', 0),
            'score_breakdown': w.get('score_breakdown', ''),
        })
    
    return jsonify({
        "success": True,
        "total_score": score,
        "compensation": comp,
        "works": works_detail
    })
