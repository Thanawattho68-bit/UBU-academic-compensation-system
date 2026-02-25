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
    timeline = load_config('timeline.json', {})
    criteria = load_config('criteria.json', [])
    if criteria is None: criteria = []
    if isinstance(criteria, dict): criteria = []
    
    # Sort for display
    if isinstance(criteria, list):
        criteria.sort(key=lambda x: str(x.get('fiscal_year', '')), reverse=True)
        
    return render_template('manage_criteria.html', criteria=criteria, name=session['name'], role=session['role'], timeline=timeline)


@admin_bp.route('/manage/timeline') # ผู้รับผิดชอบ: นายฐิติวัฒน์ กุลบุตร (กำหนดการ)
def manage_timeline():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))
    
    # Fetch from DB
    configs = query_db('SELECT * FROM FiscalYearConfig ORDER BY fiscal_year DESC')
    return render_template('manage_timeline.html', name=session['name'], role=session['role'], timelines=configs, position=session.get('position',''))


@admin_bp.route('/edit_timeline', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายฐิติวัฒน์ กุลบุตร (กำหนดการ)
def edit_timeline():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))
    
    fiscal_year = request.args.get('year')
    config = query_db('SELECT * FROM FiscalYearConfig WHERE fiscal_year = ?', (fiscal_year,), one=True)
    rounds = query_db('SELECT * FROM TimelineRound WHERE fiscal_year = ?', (fiscal_year,))
    
    # Convert rounds to list of dicts for template JS
    rounds_list = []
    for r in rounds:
        rounds_list.append({
            "name": r['round_name'],
            "type": r['round_type'],
            "start_date": r['start_date'],
            "end_date": r['end_date']
        })

    timeline_data = None
    if config:
        timeline_data = {
            "fiscal_year": config['fiscal_year'],
            "start_date": config['start_date'],
            "end_date": config['end_date'],
            "rounds": rounds_list
        }
    
    if request.method == 'POST':
        action = request.form.get('action')
        new_year = request.form.get('fiscal_year')
        
        if action == 'delete':
            execute_db('DELETE FROM FiscalYearConfig WHERE fiscal_year = ?', (fiscal_year,))
            # TimelineRound will be deleted by ON DELETE CASCADE
            flash(f"ลบข้อมูลปีงบประมาณ {fiscal_year} เรียบร้อยแล้ว")
            return redirect(url_for('admin.manage_timeline'))
            
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        rounds_json = request.form.get('rounds_data', '[]')
        
        try:
            rounds_input = json.loads(rounds_json)
        except:
            rounds_input = []
        
        # Save Config
        execute_db('''
            INSERT OR REPLACE INTO FiscalYearConfig (fiscal_year, start_date, end_date)
            VALUES (?, ?, ?)
        ''', (new_year, start_date, end_date))
        
        # Save Rounds (Delete old and re-insert)
        execute_db('DELETE FROM TimelineRound WHERE fiscal_year = ?', (new_year,))
        for r in rounds_input:
            execute_db('''
                INSERT INTO TimelineRound (fiscal_year, round_name, round_type, start_date, end_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (new_year, r.get('name'), r.get('type'), r.get('start_date'), r.get('end_date')))
            
        flash(f"บันทึกข้อมูลปีงบประมาณ {new_year} เรียบร้อยแล้ว")
        return redirect(url_for('admin.manage_timeline'))

    return render_template('edit_timeline.html', name=session['name'], role=session['role'], timeline=timeline_data, year=fiscal_year)


@admin_bp.route('/edit_criteria', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายภัทรพงษ์ จรรยากรณ์ (เกณฑ์คะแนน)
def edit_criteria():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.login'))

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
             return redirect(url_for('admin.manage_criteria'))
        
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
        return redirect(url_for('admin.manage_criteria'))

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
