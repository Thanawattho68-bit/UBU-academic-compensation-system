# ระบบเบิกจ่ายค่าตอบแทนผลงานทางวิชาการ (Academic Compensation System)

ระบบสำหรับยื่นคำขอและพิจารณาค่าตอบแทนสำหรับผลงานทางวิชาการของบุคลากรในมหาวิทยาลัย

## Tech Stack
- **Language:** Python 3.x
- **Framework:** Flask (Web Framework)
- **Database:** SQLite (sqlite3)
- **Frontend:** HTML5, Vanilla CSS, JavaScript

## การติดตั้งและเริ่มต้นใช้งาน

### 1. requirements
ต้องมี Python ติดตั้งอยู่ในเครื่องก่อน จากนั้นให้ทำการ Clone แผนกนี้ลงในเครื่อง

### 2. ติดตั้ง Library ที่จำเป็น
เปิด Terminal หรือ Command Prompt ในโฟลเดอร์โครงการแล้วรันคำสั่ง:
```bash
pip install -r requirements.txt
```

### 3. ตั้งค่าฐานข้อมูล (Database Migration)
เนื่องจากระบบเปลี่ยนจากระบบ JSON มาเป็นฐานข้อมูล SQLite เต็มรูปแบบ ให้รันสคริปต์เพื่อสร้าง Table และย้ายข้อมูล:
```bash
python migrate_data.py
```
*(หมายเหตุ: การรันสคริปต์นี้จะสร้างไฟล์ `instance/database.db` ให้โดยอัตโนมัติ)*

### 4. เริ่มรันระบบ
รันเซิร์ฟเวอร์ด้วยคำสั่ง:
```bash
python app.py
```
จากนั้นเข้าใช้งานผ่าน Browser ที่: `http://127.0.0.1:5000`

---

## โครงสร้างไฟล์ที่สำคัญ

- `app.py`: ไฟล์หลักสำหรับรันระบบและจัดการ Route ต่างๆ
- `database.py`: โมดูลสำหรับจัดการการเชื่อมต่อฐานข้อมูล SQLite และการ Query
- `migrate_data.py`: สคริปต์สำหรับย้ายข้อมูลจากระบบ JSON เข้าสู่ฐานข้อมูล SQLite
- `instance/database.db`: ไฟล์ฐานข้อมูลจริง (จะถูกสร้างอัตโนมัติ)
- `templates/`: โฟลเดอร์เก็บไฟล์ HTML (Jinja2)
- `static/`: โฟลเดอร์เก็บไฟล์ CSS, Images และ JavaScript

---

## โครงสร้างการดำเนินงานและผู้รับผิดชอบ Route

### 1. นายธนวรรธ ทองตื้อ (2 Routes)
- `@app.route('/new_request')` - แบบฟอร์มการยื่นคำขอใหม่
- `@app.route('/uploads/...')` - ระบบจัดการไฟล์อัปโหลด

### 2. นายภัทรพงษ์ จรรยากรณ์ (2 Routes + Main Logic)
- `@app.route('/manage_criteria')` - จัดการเกณฑ์คะแนน (Admin)
- `@app.route('/edit_criteria')` - แก้ไขเกณฑ์คะแนน
- *ผู้รับผิดชอบหลัก: ระบบคำนวณคะแนนอัตโนมัติ*

### 3. นางสาวฐิติรัตน์ แสงห้าว (4 Routes)
- `@app.route('/login')` - ระบบเข้าสู่ระบบ
- `@app.route('/logout')` - ระบบออกจากระบบ
- `@app.route('/')` - หน้าแรก (Entry Point)
- `@app.route('/dashboard')` - หน้าหลักผู้ใช้งานและระบบค้นหา

### 4. นายกฤษดา ตะเคียนเกลี้ยง (3 Routes)
- `@app.route('/manage/rounds')` - จัดการรอบการพิจารณา
- `@app.route('/round_history')` - ประวัติรอบการพิจารณา
- `@app.route('/view_round/<id>')` - รายละเอียดรอบการพิจารณารายครั้ง

### 5. นายฤทธิชัย โลมะกาล (3 Routes)
- `@app.route('/api/notifications')` - ระบบ API แจ้งเตือน
- `@app.route('/api/notifications/read/<id>')` - API จัดการสถานะการอ่าน
- `@app.route('/notifications')` - หน้าศูนย์รวมการแจ้งเตือน

### 6. นางสาวเบญจมาศ จ่านันท์ (2 Routes)
- `@app.route('/appeals')` - รายการอุทธรณ์ผลการพิจารณา
- `@app.route('/appeal/<id>')` - หน้าการยื่นอุทธรณ์สำหรับผู้ใช้

### 7. นายศุกลวัฒณ์ ไกรษี (2 Routes)
- `@app.route('/view_request/<id>')` - หน้าดูรายละเอียดคำขอรวม
- `@app.route('/view_work/<id>/<idx>')` - หน้าดูรายละเอียดผลงานรายชิ้น

### 8. นายฐิติวัฒน์ ลุณบุตร (2 Routes)
- `@app.route('/manage/timeline')` - จัดการกำหนดการเปิด-ปิดระบบ
- `@app.route('/edit_timeline')` - แก้ไขข้อมูล Timeline

---
