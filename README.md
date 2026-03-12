# ระบบเบิกจ่ายค่าตอบแทนผลงานทางวิชาการ (Academic Compensation System)

ระบบสำหรับยื่นคำขอและพิจารณาค่าตอบแทนสำหรับผลงานทางวิชาการของบุคลากรในมหาวิทยาลัยอุบลราชธานี

## Tech Stack

- **Language:** Python 3.x
- **Framework:** Flask (Web Framework) - ใช้ระบบ Blueprints ในการจัดการ Module
- **Database:** SQLite (sqlite3) - จัดเก็บข้อมูลถาวร (รวมถึง JSON เดิมที่ย้ายเข้า DB ทั้งหมดแล้ว)
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

เนื่องจากไฟล์ฐานข้อมูล (`instance/database.db`) ไม่ถูกเก็บไว้ใน Git เพื่อป้องกัน Conflict ผู้ใช้ใหม่ต้องสร้างฐานข้อมูลในเครื่องตนเองก่อนเริ่มงาน:

```bash
python migrate_data.py
```

_(หมายเหตุ: สคริปต์นี้จะอ่านข้อมูลเริ่มต้นจากโฟลเดอร์ `backup/` เพื่อสร้างฐานข้อมูลและโอนย้ายข้อมูลเข้าสู่ระบบใหม่โดยอัตโนมัติ)_

### 4. บัญชีผู้ใช้สำหรับการทดสอบ

รหัสผ่านเริ่มต้นสำหรับทุกบัญชีคือ `123` (หรือตามที่ระบุในไฟล์ JSON ในโฟลเดอร์ backup)

| Username       | Role           | Name                |
| :------------- | :------------- | :------------------ |
| **root**       | admin          | ผู้ดูแลระบบ         |
| **admin_work** | administration | เจ้าหน้าที่งานบุคคล |
| **research01** | research       | เจ้าหน้าที่งานวิจัย |
| **board01**    | committee      | คณะกรรมการประจำคณะ  |
| **user01**     | applicant      | ผศ. สมชาย           |

### 5. เริ่มรันระบบ

รันเซิร์ฟเวอร์ด้วยคำสั่ง:

```bash
python app.py
```

จากนั้นเข้าใช้งานผ่าน Browser ที่: `http://127.0.0.1:5001`

---

## โครงสร้างไฟล์ที่สำคัญ

- `app.py`: ไฟล์หลักสำหรับรันระบบ (Entry Point) และลงทะเบียน Blueprints
- `database.py`: โมดูลจัดการการเชื่อมต่อฐานข้อมูล SQLite และนิยามโครงสร้าง Table
- `migrate_data.py`: สคริปต์สำหรับการ Migration ข้อมูลเริ่มต้นจาก JSON เข้าสู่ Database
- `backup/`: โฟลเดอร์เก็บไฟล์ JSON ข้อมูลเบื้องต้น (Seed Data)
- `instance/`: โฟลเดอร์เก็บไฟล์ฐานข้อมูล `.db` (Git จะไม่ติดตามโฟลเดอร์นี้)
- `routes/`: โฟลเดอร์เก็บ Module แยกตาม Blueprint
  - `auth.py`: ระบบจัดการการเข้าสู่ระบบ/ออกจากระบบ
  - `main.py`: หน้าหลัก Dashboard, การแจ้งเตือน, สรุปยอด, และรายการอุทธรณ์
  - `requests.py`: ระบบยื่นคำขอใหม่, การดูรายละเอียด และระบบยื่นอุทธรณ์
  - `admin.py`: ระบบจัดการเกณฑ์คะแนน และจัดการ Timeline กำหนดวันเปิด-ปิด
  - `api.py`: ระบบ API สำหรับตรวจสอบความซ้ำซ้อน และจัดการไฟล์อัปโหลด
- `templates/`: เก็บไฟล์ HTML (Jinja2 Templates)
- `static/`: เก็บไฟล์ CSS (Modern UI), Images และ JavaScript
- `uploads/`: เก็บไฟล์หลักฐานที่ผู้ใช้ยื่นคำขอ (จะถูกสร้างอัตโนมัติแยกตาม REQ ID)

---

## รายละเอียดผู้รับผิดชอบและระบบงาน (Update 2026)

### 1. นางสาวฐิติรัตน์ แสงห้าว 68114540166 (Blueprint: `main`, `auth`)

- `@auth_bp.route('/login')` - ระบบเข้าสู่ระบบ (Login)
- `@auth_bp.route('/logout')` - ระบบออกจากระบบ (Logout)
- `@main_bp.route('/')` - หน้าแรก (Entry Point)
- `@main_bp.route('/dashboard')` - หน้าหลักผู้ใช้งาน และระบบค้นหา/กรองข้อมูลคำขอ

### 2. นายธนวรรธ ทองตื้อ 68114540258 (Blueprint: `requests`, `api`)

- `@requests_bp.route('/new_request')` - ระบบยื่นคำขอใหม่ (Smart Form Implementation)
- `@api_bp.route('/uploads/...')` - ระบบให้บริการไฟล์เอกสารหลักฐาน (Secure File Hosting)

### 3. นายศุกลวัฒณ์ ไกรษี 68114540629 (Blueprint: `requests`)

- `@requests_bp.route('/view_request/<id>')` - หน้าแสดงรายละเอียดคำขอ และประวัติการพิจารณา (Audit Trail)
- `@requests_bp.route('/view_work/<id>/<idx>')` - หน้าตรวจสอบรายละเอียดผลงานรายชิ้น

### 4. นายฤทธิชัย โลมะกาล 68114540533 (Blueprint: `main`, `api`)

- `@main_bp.route('/notifications')` - หน้าศูนย์รวมการแจ้งเตือนทั้งหมด
- `@main_bp.route('/api/notifications')` - ระบบ API ดึงข้อมูลการแจ้งเตือนแบบ Real-time
- `@main_bp.route('/api/notifications/read/<id>')` - ระบบ API อัปเดตสถานะการอ่านแจ้งเตือน

### 5. นางสาวเบญจมาศ จ่านันท์ 68114540344 (Blueprint: `main`, `requests`)

- `@main_bp.route('/appeals')` - หน้ารวมรายการอุทธรณ์สำหรับบุคลากรและคณะกรรมการ
- `@requests_bp.route('/appeal/<id>')` - แบบฟอร์มการยื่นอุทธรณ์ผลการพิจารณา

### 6. นายกฤษดา ตะเคียนเกลี้ยง 68114540065 (Blueprint: `main`, `api`)

- `@main_bp.route('/summary')` - ระบบสรุปยอดรวมของระบบ (Dashboard Statistics) และรายงานตามตำแหน่งวิชาการ
- `@api_bp.route('/api/check_work_duplicate')` - ระบบวิเคราะห์ความซ้ำซ้อนของผลงานและตรวจสอบอายุผลงาน (2 ปี)
- _(หมายเหตุ: ระบบจัดชุด Batching เดิมถูกระงับการใช้งานเพื่อความคล่องตัวของกระบวนการพิจารณา)_

### 7. นายภัทรพงษ์ จรรยากรณ์ 68114540434 (Blueprint: `admin`)

- `@admin_bp.route('/manage_criteria')` - ระบบบริหารจัดการเกณฑ์คะแนน (CRUD)
- `@admin_bp.route('/edit_criteria')` - แบบฟอร์มแก้ไขเกณฑ์คะแนนและอัตราค่าตอบแทนรายปีงบประมาณ

### 8. นายฐิติวัฒน์ ลุณบุตร 68114540814 (Blueprint: `admin`)

- `@admin_bp.route('/manage_timeline')` - ระบบจัดการ Timeline กำหนดวาระการเปิด-ปิดระบบ
- `@admin_bp.route('/edit_timeline')` - ระบบแก้ไขกำหนดการเปิดรับคำขอในแต่ละปีงบประมาณ

---
