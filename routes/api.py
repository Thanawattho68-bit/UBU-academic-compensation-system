"""
routes/api.py
จัดการ API routes และการให้บริการไฟล์ที่อัปโหลด
ผู้รับผิดชอบ:
  - นายกฤษดา ตะเคียนเกลี้ยง 68114540065 (ตรวจสอบความซ้ำซ้อน)
  - นายธนวรรธ ทองตื้อ 68114540258 (อัปโหลดไฟล์)
"""

import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, session, send_from_directory, current_app
from database import query_db, execute_db
from utils import parse_thai_date, deserialize_request, calculate_compensation

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/check_work_duplicate', methods=['POST']) # ผู้รับผิดชอบ: นายกฤษดา ตะเคียนเกลี้ยง 68114540065 (ตรวจสอบความซ้ำซ้อน)
def api_check_work_duplicate():
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    data = request.get_json()
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
            
            # ใช้วันที่เปิดรับคำขอเป็นเกณฑ์ (ถ้ามี) ถ้าไม่มีให้ใช้วันที่ปัจจุบัน
            ref_date = datetime.now()
            if current_req and current_req.get('fiscal_year'):
                timeline = query_db('SELECT start_date FROM TimelineConfig WHERE fiscal_year = ?', (str(current_req['fiscal_year']),), one=True)
                if timeline and timeline['start_date']:
                    dt_ref = parse_thai_date(timeline['start_date'])
                    if dt_ref:
                        ref_date = dt_ref

            age_years = ref_date.year - dt_pub.year
            if age_years > 2:
                is_old = True
            elif age_years == 2:
                # ถ้าห่างกัน 2 ปีพอดี ให้เช็คเดือนและวันที่ของเกณฑ์ตั้งต้น
                if ref_date.month < dt_pub.month or (ref_date.month == dt_pub.month and ref_date.day < dt_pub.day):
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
        
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], req_id, work_id), filename)


@api_bp.route('/api/estimate_compensation', methods=['POST']) #ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ 68114540419 (คำนวณคะแนน)
def api_estimate_compensation():
    """API endpoint สำหรับคำนวณคะแนนและค่าตอบแทน ใช้ logic เดียวกับ Backend"""
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    data = request.get_json()
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
