"""
routes/rounds.py
จัดการ route เกี่ยวกับรอบการพิจารณา
ผู้รับผิดชอบ: นายกฤษดา ตะเคียนเกลี้ยง (สร้างรอบพิจารณา)
"""

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import load_data, save_data, format_thai_date, calculate_compensation

rounds_bp = Blueprint('rounds', __name__)


@rounds_bp.route('/manage/rounds', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายกฤษฎา ตะเคียนเกลี้ยง (สร้างรอบพิจารณา)
def manage_rounds():
    if 'username' not in session or session['role'] not in ['administration', 'committee', 'admin']: # Committee might want to see history
         return redirect(url_for('auth.login'))
         
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
            return redirect(url_for('rounds.round_history'))

    return render_template('create_round.html', name=session['name'], role=session['role'], position=session.get('position',''), pending_reqs=pending_reqs)


@rounds_bp.route('/round_history') # ผู้รับผิดชอบ: นายกฤษฎา ตะเคียนเกลี้ยง (สร้างรอบพิจารณา)
def round_history():
    if 'username' not in session or session['role'] not in ['administration', 'committee', 'admin']: 
         return redirect(url_for('auth.login'))
         
    batches = load_data('batches.json')
    return render_template('round_history.html', name=session['name'], role=session['role'], position=session.get('position',''), batches=batches)


@rounds_bp.route('/view_round/<round_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายกฤษฎา ตะเคียนเกลี้ยง (สร้างรอบพิจารณา)
def view_round(round_id):
    if 'username' not in session: return redirect(url_for('auth.login'))
    
    batches = load_data('batches.json')
    batch = next((b for b in batches if b['id'] == round_id), None)
    if not batch:
        flash("ไม่พบข้อมูลรอบการพิจารณา")
        return redirect(url_for('main.dashboard'))
        
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
            return redirect(url_for('main.dashboard'))

    return render_template('view_round.html', batch=batch, summary=summary, role=session['role'])
