"""
routes/auth.py
จัดการ route เข้าสู่ระบบและออกจากระบบ
ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว 68114540166 (เข้าสู่ระบบ / ออกจากระบบ)
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import query_db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว 68114540166 (เข้าสู่ระบบ)
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        user = query_db('SELECT * FROM account WHERE username = ? AND password = ?', (username, password), one=True)

        if user:
            # Parse academic_position from DB (it might be a JSON string or a simple string)
            db_pos = user['academic_position']
            positions = []
            if db_pos:
                try:
                    positions = json.loads(db_pos)
                    if not isinstance(positions, list):
                        positions = [positions]
                except (json.JSONDecodeError, TypeError):
                    positions = [db_pos]
            else:
                # Default labels based on role
                default_pos = {
                    'admin': 'ผู้ดูแลระบบ',
                    'administration': 'เจ้าหน้าที่งานบุคคล',
                    'research': 'เจ้าหน้าที่งานวิจัย',
                    'committee': 'คณะกรรมการประจำคณะ',
                    'applicant': 'ผู้ยื่นคำขอ'
                }.get(user['role'], user['role'])
                positions = [default_pos]

            session.update({
                'username': user['username'], 
                'role': user['role'], 
                'name': f"{user['title_name'] or ''} {user['name'] or ''}".strip(),
                'position': positions
            })
            return redirect(url_for('main.dashboard'))
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    return render_template('login.html')


@auth_bp.route('/logout') # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว 68114540166 (ออกจากระบบ)
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
