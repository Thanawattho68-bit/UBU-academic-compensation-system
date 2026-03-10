"""
routes/admin.py
จัดการ route สำหรับผู้ดูแลระบบ: เกณฑ์คะแนน, กำหนดการ
ผู้รับผิดชอบ:
  - นายภัทรพงษ์ จรรยากรณ์ 68114540434 (Admin/เกณฑ์)
  - นายฐิติวัฒน์ ลุณบุตร 68114540814 (กำหนดการ)
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import query_db, execute_db
from utils import parse_criteria_row

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/manage_criteria') # ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ 68114540434 (Admin/เกณฑ์)
def manage_criteria():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))
    
    # Fetch from DB
    rows = query_db('SELECT * FROM Criteria ORDER BY fiscal_year DESC')
    criteria = [parse_criteria_row(r) for r in rows]
        
    return render_template('manage_criteria.html', criteria=criteria, name=session['name'], role=session['role'])


@admin_bp.route('/edit_criteria', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ 68114540434 (เกณฑ์คะแนน)
def edit_criteria():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))

    fiscal_year = request.args.get('year')
    row = query_db('SELECT * FROM Criteria WHERE fiscal_year = ?', (fiscal_year,), one=True)
    criteria_data = parse_criteria_row(row) if row else None

    if request.method == 'POST':
        action = request.form.get('action')
        new_year = request.form.get('fiscal_year')
        
        if action == 'delete':
            execute_db('DELETE FROM Criteria WHERE fiscal_year = ?', (fiscal_year,))
            flash(f"ลบข้อมูลปีงบประมาณ {fiscal_year} เรียบร้อยแล้ว")
            return redirect(url_for('admin.manage_criteria'))
        
        def to_float(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        def get_tiers(pos_key):
            tiers = []
            for i in range(2):
                min_s = request.form.get(f'{pos_key}_min_{i}')
                amt = request.form.get(f'{pos_key}_amt_{i}')
                if min_s is not None and amt is not None and min_s.strip() != "":
                    tiers.append({"min_score": to_float(min_s), "amount": to_float(amt)})
            return tiers

        quality_scores = {
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
            }
        }
        role_weights = {
            "main": to_float(request.form.get('role_main')),
            "co": to_float(request.form.get('role_co'))
        }
        payment_rules = {
            "asst_prof": get_tiers('asst'),
            "assoc_prof": get_tiers('assoc'),
            "prof": get_tiers('prof')
        }
        
        execute_db('''
            INSERT OR REPLACE INTO Criteria (fiscal_year, quality_scores, role_weights, payment_rules)
            VALUES (?, ?, ?, ?)
        ''', (new_year, json.dumps(quality_scores, ensure_ascii=False), json.dumps(role_weights, ensure_ascii=False), json.dumps(payment_rules, ensure_ascii=False)))
        
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('admin.manage_criteria'))

    if not criteria_data:
        # Default Template
        criteria_data = {
            "fiscal_year": "",
            "quality_scores": {
                "research": {"tier1": 1.25, "non_q": 1.00, "national": 0.75},
                "merged_abc": {"a_plus": 1.25, "a": 1.00, "b": 0.75},
                "textbook": {"publisher": 1.25, "general": 1.00},
                "creative": {"international": 1.25, "cooperation": 1.00, "national": 0.75}
            },
            "role_weights": {"main": 1.0, "co": 0.5},
            "payment_rules": {
                "asst_prof": [{"min_score": 0.50, "amount": 3000}, {"min_score": 0.75, "amount": 5600}],
                "assoc_prof": [{"min_score": 0.75, "amount": 6000}, {"min_score": 1.25, "amount": 9900}],
                "prof": [{"min_score": 1.25, "amount": 9000}, {"min_score": 1.50, "amount": 13000}]
            }
        }

    return render_template('edit_criteria.html', data=criteria_data, name=session['name'], role=session['role'])


@admin_bp.route('/manage_timeline') # ผู้รับผิดชอบ: นายฐิติวัฒน์ ลุณบุตร 68114540814 (กำหนดการ)
def manage_timeline():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))
    
    # Fetch all from DB
    rows = query_db('SELECT * FROM TimelineConfig ORDER BY fiscal_year DESC')
    timelines = []
    for r in rows:
        t = dict(r)
        t['rounds'] = json.loads(t['rounds_json']) if t.get('rounds_json') else []
        timelines.append(t)
        
    return render_template('manage_timeline.html', timelines=timelines, name=session['name'], role=session['role'])


@admin_bp.route('/edit_timeline', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายฐิติวัฒน์ ลุณบุตร 68114540814 (กำหนดการ)
def edit_timeline():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))

    year = request.args.get('year')
    row = query_db('SELECT * FROM TimelineConfig WHERE fiscal_year = ?', (year,), one=True)
    
    timeline_data = None
    if row:
        timeline_data = dict(row)
        timeline_data['rounds'] = json.loads(timeline_data['rounds_json']) if timeline_data.get('rounds_json') else []

    if request.method == 'POST':
        action = request.form.get('action')
        fiscal_year = request.form.get('fiscal_year')
        
        if action == 'delete':
            execute_db('DELETE FROM TimelineConfig WHERE fiscal_year = ?', (fiscal_year,))
            flash(f"ลบข้อมูลปีงบประมาณ {fiscal_year} เรียบร้อยแล้ว")
            return redirect(url_for('admin.manage_timeline'))
        
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        rounds_json = request.form.get('rounds_data', '[]')
        
        execute_db('''
            INSERT OR REPLACE INTO TimelineConfig (fiscal_year, start_date, end_date, rounds_json)
            VALUES (?, ?, ?, ?)
        ''', (fiscal_year, start_date, end_date, rounds_json))
        
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('admin.manage_timeline'))

    return render_template('edit_timeline.html', timeline=timeline_data, year=year, name=session['name'], role=session['role'])
