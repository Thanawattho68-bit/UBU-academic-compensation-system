"""
routes/api.py
จัดการ API routes และการให้บริการไฟล์ที่อัปโหลด
ผู้รับผิดชอบ:
  - นายศุภวัฒน์ ไกรศา (ตรวจสอบความซ้ำซ้อน)
  - นายธนวรรธ ทองตื้อ (เพิ่ม/ลบประเภทผลงาน, อัปโหลดไฟล์)
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify, session, send_from_directory, current_app
from utils import load_data, save_data, parse_thai_date

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/check_work_duplicate', methods=['POST']) # ผู้รับผิดชอบ: นายศุภวัฒน์ โกรธา (ตรวจสอบความซ้ำซ้อน)
def api_check_work_duplicate():
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    data = request.get_json()
    title = data.get('title', '').strip()
    date_publish_str = data.get('date_publish', '')
    req_id = data.get('req_id', '')

    if not title:
        return jsonify({"success": False, "message": "กรุณาระบุชื่อผลงาน"})

    all_reqs = load_data('requests.json')
    
    self_duplicates = []
    shared_works = []
    
    current_req = next((r for r in all_reqs if r['id'] == req_id), None)
    current_username = current_req['applicant'] if current_req else session['username']

    for r in all_reqs:
        # Skip checking against its own items if same request ID
        # (Though we check titles, and one request can have multiple works)
        # But usually we check against OTHER requests/years
        if r['id'] == req_id:
            # We skip checking against other works in the SAME request for now
            # unless instructed otherwise. Usually duplicate check is across historical data.
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
                if r['applicant'] == current_username:
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
            # Simple year difference
            age_years = now.year - dt_pub.year
            # Check if it's more than 2 years
            if age_years > 2:
                is_old = True
            # For exact 2-year boundary, could check months
            elif age_years == 2:
                if now.month < dt_pub.month or (now.month == dt_pub.month and now.day < dt_pub.day):
                    # Not yet fully 2 years
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


@api_bp.route('/api/add_work_type', methods=['POST']) # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ (เพิ่มประเภทผลงาน)
def api_add_work_type():
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    data = request.get_json()
    label = data.get('label', '').strip()
    if not label:
        return jsonify({"success": False, "message": "กรุณาระบุชื่อประเภทผลงาน"})
    
    work_types = load_data('work_types.json')
    
    # Check for duplicate label
    if any(wt['label'] == label for wt in work_types):
        return jsonify({"success": False, "message": "ประเภทผลงานนี้มีอยู่แล้วในระบบ"})
    
    # Generate unique ID
    new_id = f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_type = {"id": new_id, "label": label, "is_custom": True}
    work_types.append(new_type)
    save_data('work_types.json', work_types)
    
    return jsonify({"success": True, "type": new_type})


@api_bp.route('/api/delete_work_type', methods=['POST']) # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ (ลบประเภทผลงาน)
def api_delete_work_type():
    if 'username' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    
    data = request.get_json()
    type_id = data.get('id', '')
    
    work_types = load_data('work_types.json')
    target = next((wt for wt in work_types if wt['id'] == type_id), None)
    
    if not target:
        return jsonify({"success": False, "message": "ไม่พบประเภทผลงานที่ต้องการลบ"})
    
    if not target.get('is_custom'):
        return jsonify({"success": False, "message": "ไม่สามารถลบประเภทผลงานหลักของระบบได้"})
    
    work_types = [wt for wt in work_types if wt['id'] != type_id]
    save_data('work_types.json', work_types)
    
    return jsonify({"success": True})


@api_bp.route('/uploads/<req_id>/<work_id>/<filename>') # ผู้รับผิดชอบ: นาย ธนวรรธ ทองตื้อ (อัปโหลดไฟล์)
def uploaded_file(req_id, work_id, filename):
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], req_id, work_id), filename)
