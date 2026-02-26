# ระบบเบิกจ่ายค่าตอบแทนผลงานทางวิชาการ (Academic Compensation System)

ระบบสำหรับยื่นคำขอและพิจารณาค่าตอบแทนสำหรับผลงานทางวิชาการของบุคลากรในมหาวิทยาลัยอุบลราชธานี

## Tech Stack
- **Language:** Python 3.x
- **Framework:** Flask (Web Framework) - ใช้ระบบ Blueprints ในการจัดการ Module
- **Database:** SQLite (sqlite3) - เปลี่ยนจากระบบ JSON มาเป็น Database เต็มรูปแบบ
- **Frontend:** HTML5, Vanilla CSS (Modern Design), JavaScript
- **Templates:** Jinja2

## การติดตั้งและเริ่มต้นใช้งาน

### 1. Requirements
ต้องมี Python 3.x ติดตั้งอยู่ในเครื่องก่อน จากนั้นให้ทำการ Clone Project นี้ลงในเครื่อง

### 2. ติดตั้ง Library ที่จำเป็น
เปิด Terminal ในโฟลเดอร์โครงการแล้วรันคำสั่ง:
```bash
pip install -r requirements.txt
```

### 3. ตั้งค่าฐานข้อมูล (Database Migration)
หากเป็นการรันครั้งแรก หรือต้องการอัปเดตโครงสร้าง Table ให้รันสคริปต์ Migration:
```bash
python migrate_data.py
```
*(หมายเหตุ: สคริปต์นี้จะสร้างไฟล์ `instance/database.db` และโอนย้ายข้อมูลจากไฟล์ JSON เดิมเข้าสู่ระบบฐานข้อมูล)*

### 4. เริ่มรันระบบ
รันเซิร์ฟเวอร์ด้วยคำสั่ง:
```bash
python app.py
```
จากนั้นเข้าใช้งานผ่าน Browser ที่: `http://127.0.0.1:5001`

---

## โครงสร้างไฟล์ที่สำคัญ

- `app.py`: ไฟล์หลักสำหรับรันระบบ (Entry Point) และลงทะเบียน Blueprints
- `database.py`: โมดูลจัดการการเชื่อมต่อฐานข้อมูล SQLite 
- `migrate_data.py`: สคริปต์สำหรับการ Migration ข้อมูล
- `routes/`: โฟลเดอร์เก็บ Module แยกตาม Blueprint
  - `auth.py`: ระบบจัดการการเข้าสู่ระบบ/ออกจากระบบ
  - `main.py`: หน้าหลัก Dashboard และการแจ้งเตือน
  - `requests.py`: ระบบยื่นคำขอและตรวจสอบคำขอ
  - `admin.py`: ระบบจัดการเกณฑ์คะแนนสำหรับผู้ดูแลระบบ
  - `api.py`: ระบบ API สำหรับตรวจสอบความซ้ำซ้อนและจัดการประเภทผลงาน
- `templates/`: เก็บไฟล์ HTML (Jinja2 Templates)
- `static/`: เก็บไฟล์ CSS, Images และ JavaScript
- `uploads/`: เก็บไฟล์หลักฐานที่ผู้ใช้ยื่นคำขอ (จะถูกสร้างอัตโนมัติ)

---

## รายละเอียดผู้รับผิดชอบและระบบงาน (Update 2026)

### 1. นางสาวฐิติรัตน์ แสงห้าว (Blueprint: `main`)
- `@main_bp.route('/')` - หน้าแรก (Gateway เช็คสิทธิ์การเข้าใช้งาน)
- `@main_bp.route('/dashboard')` - หน้าหลักผู้ใช้งานและระบบค้นหาข้อมูลคำขอ

### 2. นาย ธนวรรธ ทองตื้อ (Blueprint: `auth`, `requests`, `api`)
- `@auth_bp.route('/login')` - ระบบเข้าสู่ระบบ
- `@auth_bp.route('/logout')` - ระบบออกจากระบบ
- `@requests_bp.route('/new_request')` - แบบฟอร์มยื่นคำขอใหม่ (Form Logic)
- `@api_bp.route('/api/add_work_type')` - ระบบเพิ่มประเภทผลงานทางวิชาการ
- `@api_bp.route('/uploads/...')` - ระบบจัดการไฟล์หลักฐานที่อัปโหลด

### 3. นายศุภวัฒน์ ไกรศา (Blueprint: `requests`, `api`)
- `@requests_bp.route('/view_request/<id>')` - หน้าดูรายละเอียดคำขอรวม
- `@requests_bp.route('/view_work/<id>/<idx>')` - หน้าตรวจสอบรายละเอียดผลงานรายชิ้น
- `@api_bp.route('/api/check_work_duplicate')` - ระบบตรวจสอบความซ้ำซ้อนของผลงาน

### 4. นายฤทธิชัย โสนะกาล (Blueprint: `main`)
- `@main_bp.route('/api/notifications')` - API ดึงข้อมูลแจ้งเตือน
- `@main_bp.route('/notifications')` - หน้าศูนย์รวมการแจ้งเตือนทั้งหมด

### 5. นางสาวเบญจมาศ จ่านันท์ (Blueprint: `main`, `requests`)
- `@main_bp.route('/appeals')` - รายการอุทธรณ์ผลการพิจารณา
- `@requests_bp.route('/appeal/<id>')` - หน้าการยื่นอุทธรณ์สำหรับผู้ใช้งาน

### 6. นายภัทรพงษ์ จรรยากรณ์ (Blueprint: `admin`)
- `@admin_bp.route('/manage_criteria')` - หน้าจัดการเกณฑ์คะแนน (Admin)
- `@admin_bp.route('/edit_criteria')` - ระบบแก้ไขเกณฑ์คะแนนและอัตราการจ่ายเงิน

### 7. นายกฤษฎา ตะเคียนเกลี้ยง (Blueprint: `rounds`)
- *@หมายเหตุ: ปัจจุบันระบบจัดชุด (Batching) ถูกระงับการใช้งานผ่าน app.py ชั่วคราว*
- `@rounds_bp.route('/manage/rounds')` - ระบบจัดการรอบการพิจารณา
- `@rounds_bp.route('/round_history')` - ประวัติรอบการพิจารณา

### 8. นายฐิติวัฒน์ ลุณบุตร (Blueprint: `admin`)
- *ผู้รับผิดชอบระบบจัดการ Timeline (กำหนดการเปิด-ปิดระบบ)*
- (อยู่ระหว่างการปรับปรุงระบบเข้าสู่ระบบฐานข้อมูลใหม่)

---
