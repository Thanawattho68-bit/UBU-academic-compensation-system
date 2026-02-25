"""
routes/auth.py
จัดการ route เข้าสู่ระบบและออกจากระบบ
ผู้รับผิดชอบ: นาย ธนวรรธ ทองตื้อ (เข้าสู่ระบบ / ออกจากระบบ)
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import query_db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นาย ธนวรรธ ทองตื้อ (เข้าสู่ระบบ)
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        user = query_db('SELECT * FROM account WHERE username = ? AND password = ?', (username, password), one=True)

        if user:
            session.update({
                'username': user['username'], 
                'role': user['role'], 
                'name': f"{user['title_name'] or ''} {user['name'] or ''}".strip(),
                'position': user['academic_position'] or {
                    'admin': 'ผู้ดูแลระบบ',
                    'administration': 'เจ้าหน้าที่งานบุคคล',
                    'research': 'เจ้าหน้าที่งานวิจัย',
                    'committee': 'คณะกรรมการประจำคณะ',
                    'applicant': 'ผู้ยื่นคำขอ'
                }.get(user['role'], user['role'])
            })
            return redirect(url_for('main.dashboard'))
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    return render_template('login.html')


@auth_bp.route('/logout') # ผู้รับผิดชอบ: นาย ธนวรรธ ทองตื้อ (ออกจากระบบ)
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
