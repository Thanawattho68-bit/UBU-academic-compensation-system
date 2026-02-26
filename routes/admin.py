"""
routes/admin.py
จัดการ route สำหรับผู้ดูแลระบบ: เกณฑ์คะแนน, กำหนดการ
ผู้รับผิดชอบ:
  - นายภัทรพงษ์ จรรยากรณ์ (Admin/เกณฑ์)
  - นายฐิติวัฒน์ กุลบุตร (กำหนดการ)
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import query_db, execute_db
from utils import load_config, save_data

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/manage_criteria') # ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ (Admin/เกณฑ์)
def manage_criteria():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))
    
    # Fetch from DB
    rows = query_db('SELECT * FROM Criteria ORDER BY fiscal_year DESC')
    criteria = []
    for r in rows:
        c = dict(r)
        c['quality_scores'] = json.loads(c['quality_scores']) if r.get('quality_scores') else {}
        c['role_weights'] = json.loads(c['role_weights']) if r.get('role_weights') else {}
        c['payment_rules'] = json.loads(c['payment_rules']) if r.get('payment_rules') else {}
        criteria.append(c)
        
    return render_template('manage_criteria.html', criteria=criteria, name=session['name'], role=session['role'])


@admin_bp.route('/edit_criteria', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ (เกณฑ์คะแนน)
def edit_criteria():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))

    fiscal_year = request.args.get('year')
    row = query_db('SELECT * FROM Criteria WHERE fiscal_year = ?', (fiscal_year,), one=True)
    
    criteria_data = None
    if row:
        criteria_data = dict(row)
        criteria_data['quality_scores'] = json.loads(criteria_data['quality_scores']) if criteria_data.get('quality_scores') else {}
        criteria_data['role_weights'] = json.loads(criteria_data['role_weights']) if criteria_data.get('role_weights') else {}
        criteria_data['payment_rules'] = json.loads(criteria_data['payment_rules']) if criteria_data.get('payment_rules') else {}

    if request.method == 'POST':
        action = request.form.get('action')
        new_year = request.form.get('fiscal_year')
        
        if action == 'delete':
            execute_db('DELETE FROM Criteria WHERE fiscal_year = ?', (fiscal_year,))
            flash(f"ลบข้อมูลปีงบประมาณ {fiscal_year} เรียบร้อยแล้ว")
            return redirect(url_for('admin.manage_criteria'))
        
        def to_float(val):
            try: return float(val)
            except: return 0.0

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
