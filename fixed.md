# สรุปการแก้ไขและปรับปรุงโค้ด

## 1. UI/UX

### คะแนนและค่าตอบแทน – รูปแบบตัวเลขและตำแหน่ง

| แก้ไข | ไฟล์ | รายละเอียด | เหตุผล |
|------|------|------------|--------|
| รูปแบบคะแนน | `app.py` | เพิ่ม filter `format_score` แทน `"%.3f"` → ใช้ `"{:,.2f}"` | ลดความสับสนระหว่าง 12.000 (สิบสอง) กับ 12,000 (หมื่นสอง) |
| ประเภทผลงานว่าง | `app.py` | ใน `translate_work_type` ถ้าไม่มี type คืน `'-'` | ป้องกันเซลล์ว่างเมื่อข้อมูลไม่ครบ |
| คะแนนงานที่ถูกปฏิเสธ | `templates/dashboard.html` | แสดง `-` เมื่อสถานะเป็น ไม่อนุมัติ/ผลงานซ้ำซ้อน | ให้เห็นชัดว่าไม่มีการให้คะแนน |
| คอลัมน์คะแนนชิดขวา | `templates/dashboard.html`, `static/style.css` | ใส่ `text-align: right` และ `.table-item-list.score-list` ชิดขวา | ตัวเลขอ่านง่ายขึ้น |
| คอลัมน์ค่าตอบแทนชิดขวา | `templates/dashboard.html` | ใส่ `text-align: right` | ให้ "-" และตัวเลขชิดขวาสม่ำเสมอ |

### Zebra striping ตาราง

| แก้ไข | ไฟล์ | รายละเอียด |
|------|------|------------|
| สีแถวสลับ | `static/style.css` | แถวคี่ขาว, แถวคู่ `#f8fafc`, hover `#f1f8ff` |

### เตือนเมื่อไฟล์เกิน 16 MB

| แก้ไข | ไฟล์ | รายละเอียด |
|------|------|------------|
| ตรวจขนาดไฟล์ | `templates/work_evidence_footer.html` | เพิ่ม `onchange="checkFileSize(this)"` ที่ input ไฟล์ |
| ฟังก์ชัน checkFileSize | `templates/new_request.html` | ตรวจขนาดก่อน upload แสดง SweetAlert และเคลียร์ input ถ้าเกิน 16 MB |

---

## 2. Backend Refactor

### `utils/helpers.py`

| แก้ไข | รายละเอียด | ผลดี |
|------|------------|------|
| ลบคอมเมนต์ซ้ำ | บรรทัด "3. Apply status logic" ซ้ำ 2 ครั้ง | โค้ดอ่านง่ายขึ้น |
| `_get_pos_key(positions)` | แยกฟังก์ชันแปลงตำแหน่ง → key (asst_prof, assoc_prof, prof) | ลดการเขียนซ้ำใน `calculate_compensation` และ `recalculate_total_only` |
| `parse_criteria_row(row)` | แปลง Criteria row จาก DB ให้ `quality_scores`, `role_weights`, `payment_rules` เป็น dict | ใช้ร่วมกันได้หลาย route ไม่ต้อง parse JSON ซ้ำ |
| `calculate_compensation` | ใช้ `parse_criteria_row` และ `_get_pos_key` | โครงสร้างโค้ดชัดและสั้นลง |
| `recalculate_total_only` | ใช้ `parse_criteria_row` และ `_get_pos_key` | เหมือนกัน ลดความซ้ำซ้อน |

### `routes/requests.py`

| แก้ไข | รายละเอียด | ผลดี |
|------|------------|------|
| ลบ `import shutil` ซ้ำ | เคย import ภายในฟังก์ชัน cancel แม้ import ที่บนไฟล์แล้ว | โค้ดสะอาดขึ้น |
| `view_request` | ใช้ `deserialize_request(row)` แทนการตั้งค่า req_data เอง แล้ว override เฉพาะ `works` กรณี draft | ใช้ logic เดียวกับส่วนอื่น ลดความซ้ำซ้อน |
| `appeal_request` | ใช้ `deserialize_request(row)` แทน `dict(row)` + parse works เอง | สอดคล้องกับ view_request |
| `new_request` | โหลด criteria ด้วย `parse_criteria_row` | ลด loop parse JSON ใน route |
| `view_request` | โหลด criteria ด้วย `parse_criteria_row` | ใช้ logic ร่วมกัน ดูแลง่ายขึ้น |

### `routes/admin.py`

| แก้ไข | รายละเอียด | ผลดี |
|------|------------|------|
| `manage_criteria` | ใช้ `[parse_criteria_row(r) for r in rows]` แทน loop แยก | โค้ดสั้นและอ่านง่ายขึ้น |
| `edit_criteria` | ใช้ `parse_criteria_row(row)` แทนการ parse แต่ละ field เอง | ใช้ helper เดียวกันทั้งระบบ |

### `app.py`

| แก้ไข | รายละเอียด | ผลดี |
|------|------------|------|
| `format_score` | จาก `if abs(f) >= 1000 ... else ...` → ใช้ `'{:,.2f}'.format(float(val))` | โค้ดสั้นขึ้น ลดเงื่อนไขที่ซับซ้อน |

### `utils/__init__.py`

| แก้ไข | รายละเอียด |
|------|------------|
| export | เพิ่ม `parse_criteria_row` ให้ import ได้จาก utils |

---

## 3. แก้บัคและจุดเสี่ยง (รอบ 2)

### `routes/api.py`

| แก้ไข | รายละเอียด | เหตุผล |
|------|------------|--------|
| เพิ่ม import | `from werkzeug.utils import secure_filename` | ใช้ secure_filename โดยไม่มี import → crash ตอนเข้า /uploads/ |
| เพิ่ม role check | `api_add_work_type`, `api_delete_work_type` ตรวจ `session.get('role') == 'admin'` | เดิมผู้ใช้ทั่วไปสามารถเพิ่ม/ลบประเภทผลงานได้ |
| ป้องกัน get_json เป็น None | ใช้ `request.get_json(silent=True) or {}` ทุก endpoint | ถ้า body ไม่ใช่ JSON จะได้ `None` แล้ว `.get()` ทำให้เกิด AttributeError |

### `routes/requests.py`

| แก้ไข | รายละเอียด | เหตุผล |
|------|------------|--------|
| ตรวจ work_index | ตรวจ `work_index < 0` หรือ `>= len(works)` ก่อนใช้ | URL เช่น /view_work/REQ-1/99 ทำให้ IndexError |
| JSON parse works_data | ใช้ try/except จับ `JSONDecodeError`, `TypeError` | works_data เสียจะทำให้เกิด 500 |

### `timeline_utils.py`

| แก้ไข | รายละเอียด | เหตุผล |
|------|------------|--------|
| เพิ่ม imports | `datetime`, `load_config`, `get_current_fiscal_year`, `parse_thai_date` จาก utils | โมดูลใช้ฟังก์ชันเหล่านี้โดยไม่ได้ import → NameError ตอน import |

---

## 4. return_date / rejection_date และจำกัด 7 วัน

### database.py
| แก้ไข | รายละเอียด |
|------|------------|
| Migration | เพิ่มคอลัมน์ `return_date`, `rejection_date` ใน `RequestRecord` |

### routes/requests.py (return_date/rejection_date)
| แก้ไข | รายละเอียด |
|------|------------|
| action `return` | บันทึก `return_date` เมื่อส่งคืนแก้ไข |
| action `reject` (งานบุคคล) | บันทึก `rejection_date` เมื่อไม่อนุมัติ |
| committee publish | บันทึก `rejection_date` เมื่อ `final_status` เป็น `ไม่อนุมัติ` หรือ `อนุมัติบางส่วน` |
| edit_remaining | คำนวณจาก `return_date` เมื่อ status = แก้ไข |
| appeal_remaining | คำนวณจาก `rejection_date` เมื่อ status = ไม่อนุมัติ/อนุมัติบางส่วน |
| submit (แก้ไข) | ตรวจสอบ edit_remaining < 0 ก่อนอนุญาต ส่งกลับ |
| submit_appeal | ตรวจสอบ appeal_remaining < 0 ก่อนอนุญาต ยื่นอุทธรณ์ |

### templates/view_request.html
| แก้ไข | รายละเอียด |
|------|------------|
| Banner แก้ไข | แสดง "ท่านมีเวลาดำเนินการอีก X วัน" หรือ "เกินกำหนดเวลา" เมื่อหมดเวลา |
| Banner อุทธรณ์ | แสดง "ท่านมีเวลายื่นอุทธรณ์อีก X วัน" หรือ "เกินกำหนดเวลา" เมื่อหมดเวลา |
| ปุ่มส่งคำขอ | ปิดการใช้งาน (disabled) เมื่อ edit_remaining < 0 |
| ปุ่มส่งอุทธรณ์ | ซ่อนเมื่อ appeal_remaining < 0 |

---

## 5. ลดความซับซ้อน (Complexity Reduction)

### constants
| ไฟล์ | รายละเอียด |
|------|------------|
| `utils/constants.py` | สร้างโมดูล constants เก็บสถานะคำขอ (STATUS_DRAFT, STATUS_EDIT ฯลฯ) สถานะงาน (WORK_APPROVED ฯลฯ) และบทบาท เพื่อลด magic strings |

### แยก handlers ตาม role
| ไฟล์ | รายละเอียด |
|------|------------|
| `routes/request_handlers.py` | แยก logic view_request POST เป็น `handle_applicant`, `handle_administration`, `handle_research`, `handle_committee` ลดฟังก์ชันหลักจาก ~310 บรรทัด เป็น ~20 บรรทัด |
| `routes/requests.py` | ใช้ handlers แทน if/elif ซ้อนหลายชั้น; dispatch ตาม role ชัดเจน |

### Error handling และ helpers
| ไฟล์ | รายละเอียด |
|------|------------|
| `utils/helpers.py` | เพิ่ม `safe_int`, `_safe_json_loads`; แก้ `except:` เป็น `except (ValueError, TypeError)` ฯลฯ; deserialize_request ใช้ _safe_json_loads ป้องกัน invalid JSON |
| `routes/admin.py` | แก้ `except:` เป็น `except (ValueError, TypeError)` ใน to_float |
| `timeline_utils.py` | แก้ `except:` เป็น `except (KeyError, TypeError)` |
| `routes/request_handlers.py` | ใช้ `safe_int` แทน `int()` เพื่อป้องกัน ValueError จาก form |

---

## 6. สรุปผลลัพธ์

- โค้ดสั้นลงจาก consolidation และ helper functions
- ลดการซ้ำซ้อนของการ parse JSON และการแปลงตำแหน่ง
- โครงสร้างชัดเจนขึ้น ใช้ helper ร่วมกันหลายจุด
- แก้จุดที่อาจทำให้สับสน (รูปแบบตัวเลข การจัดตำแหน่งคอลัมน์)
- แก้บัคที่ทำให้ crash (import, index, JSON, get_json)
- เสริมการตรวจสิทธิ์สำหรับ API เพิ่ม/ลบประเภทผลงาน
- จำกัด 7 วันสำหรับส่งคืนแก้ไขและยื่นอุทธรณ์ พร้อมแสดง remaining days และปิดปุ่มเมื่อหมดเวลา
- ลดความซับซ้อน view_request โดยแยก handlers ตาม role ใช้ constants และแก้ bare except

---

## 7. รายงานการวิเคราะห์โปรเจกต์เพิ่มเติม (สิ่งที่ควรแก้ต่อไป)

### 7.1 ความสำคัญสูง (ควรแก้ก่อน)

| รายการ | ไฟล์ | รายละเอียด |
|--------|------|------------|
| Secret key แบบ hardcode | `app.py`:20 | ใช้ `"academic_secret_key"` ควรดึงจาก env เช่น `os.environ.get('SECRET_KEY', 'dev-fallback')` |
| รหัสผ่านเก็บแบบ plain text | `database.py`, `auth.py` | ไม่มีการ hash (bcrypt/argon2) เสี่ยงมากถ้า DB รั่วไหล |
| ไม่มี CSRF protection | ทุก form | POST ไม่มี CSRF token เสี่ยง CSRF attacks |
| Connection leak ใน database | `database.py`:111-124 | `query_db` / `execute_db` ถ้า `execute` / `commit` error จะไม่ถึง `conn.close()` ควรใช้ try/finally |
| api_check_work_duplicate โหลดทุกคำขอ | `routes/api.py`:33-34 | `SELECT * FROM RequestRecord` + deserialize ทั้งหมด ถ้ามีคำขอเยอะจะช้า ควร query เฉพาะที่จำเป็น หรือตรวจ duplicate ใน SQL |
| Config แบบ hardcode | `app.py` | `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH` ควรมาจาก env หรือ config file |
| ไม่มี application logging | ทั้งโปรเจกต์ | ใช้ `print` ในการ migrate เท่านั้น ควรใช้ `logging` สำหรับ errors และเหตุการณ์สำคัญ |

### 7.2 ความสำคัญกลาง

| รายการ | ไฟล์ | รายละเอียด |
|--------|------|------------|
| appeal_request form ไม่บันทึกข้อมูล | `routes/requests.py`:550-551 | form มี `reason`, `evidence_link` แต่ POST แค่เปลี่ยน status ไม่ได้เก็บลง DB |
| ValueError จาก int() | `routes/requests.py` | `int(i)` จาก `getlist()` อาจได้ค่าที่แปลงไม่ได้ ควรใช้ try/except |
| Bare except | `helpers.py`, `requests.py`, `admin.py` | `except:` ไม่ระบุ exception ทำให้ debug ยาก |
| deserialize_request ไม่จัดการ invalid JSON | `utils/helpers.py`:59-61 | ถ้า `works_json` เป็น invalid JSON จะเกิด `JSONDecodeError` โดยไม่มีการ handle |
| Query Criteria ซ้ำ | `helpers.py`, `requests.py` | `calculate_compensation` / `recalculate_total_only` query Criteria ทุกครั้ง อาจ cache หรือส่งเป็นพารามิเตอร์ |
| ไม่มี generic error handler | `app.py` | มีแค่ handler 413 ควรมี 500 และหน้า error ที่เป็นมิตร |
| Magic strings สถานะ | หลายไฟล์ | `'แบบร่าง'`, `'ส่งแล้ว'` ฯลฯ ควรย้ายเป็น constants |
| ไม่มี unit tests | - | ไม่มี tests สำหรับ `calculate_compensation`, `parse_thai_date` และ business logic สำคัญ |

### 7.3 ความสำคัญต่ำ

| รายการ | รายละเอียด |
|--------|------------|
| log_history แบบ read-modify-write | อาจมี race condition ถ้ามี concurrent updates |
| req_id อาจซ้ำ | `REQ-{year}{mmddHMS}` อาจซ้ำถ้ามีคำขอในวินาทีเดียวกัน (โอกาสต่ำ) |
| TimelineConfig query ใน context_processor | ถูกเรียกทุก request อาจ cache per-request |
| Magic number 7 วัน | `get_remaining_days(limit_days=7)` ควรดึงจาก config |
| โครงสร้าง timeline แยกกัน | `timeline_utils.py` vs logic หลัก อาจเป็น dead code |

### 7.4 หมายเหตุเรื่อง appeal flow

- **appeal_request** (`/appeal/<req_id>`): เฉพาะสถานะ `ไม่อนุมัติ` มี form `reason` + `evidence_link` แต่ยังไม่เก็บลง DB
- **view_request submit_appeal**: รองรับทั้ง `ไม่อนุมัติ` และ `อนุมัติบางส่วน` เลือกงานเป็นรายการ + บันทึก `appeal_comment`

**ตัดสินใจที่ต้องทำ:**

1. ต้องการให้ appeal_request เก็บ `reason` และ `evidence_link` ลง DB หรือไม่
2. ต้องการให้ appeal_request รองรับสถานะ `อนุมัติบางส่วน` ด้วยหรือไม่ (หรือให้ใช้แค่ view_request)

---

### 7.5 คำอธิบายประกอบ (รายละเอียด)

#### หน้าเว็บมี แต่หลังบ้านยังไม่ทำ

| รายการ | สถานะปัจจุบัน | สิ่งที่ขาด |
|--------|----------------|------------|
| **appeal_request form** | หน้า `/appeal/<req_id>` มีฟอร์มกรอก "เหตุผลในการขออุทธรณ์" และ "ลิงค์หลักฐานเพิ่มเติม" ให้ผู้ใช้กรอกครบ | Backend POST แค่เปลี่ยน status เป็น `รอการอุทธรณ์` ไม่ได้อ่านค่า `reason` และ `evidence_link` จาก form ไปบันทึกลง DB เลย ทำให้กรรมการไม่เห็นเหตุผล/หลักฐานที่ผู้ยื่นกรอก → **ควรเพิ่มคอลัมน์ใน RequestRecord (หรือตารางแยก) เก็บ appeal_reason, appeal_evidence_link แล้วบันทึกตอน POST** |
| **role_status_label** | Template มีการแสดงสถานะหลายรูปแบบตาม role | บางสถานะอาจไม่มี mapping ชัดเจน ควรตรวจสอบว่า dict ใน `app.py` ครอบคลุมทุกกรณี |

#### ทำไมต้องมี / ทำไมละเอียดอ่อน (ตัดสินใจระมัดระวัง)

| รายการ | เหตุผลและข้อควรพิจารณา |
|--------|------------------------|
| **รหัสผ่านแบบ hash** | ถ้าเปลี่ยนเป็น bcrypt/argon2 ผู้ใช้ที่ลงทะเบียนไว้แล้วจะ login ไม่ได้ทันที (เพราะเดิมเทียบ plain text กับ DB) ต้องมี **migration** แปลงรหัสเดิม หรือ **บังคับ reset password** เมื่อ login ครั้งแรกหลังอัปเกรด → ตัดสินใจว่าจะทำทีเดียวทั้งระบบ หรือทยอย (เช่น เก็บทั้ง plain + hash ชั่วคราว) |
| **CSRF protection** | ต้องใส่ CSRF token ในทุก form ที่ POST ถ้าเพิ่ม Flask-WTF จะกระทบทุก template ที่มี `<form>` → ต้องทดสอบ flow หลักทุกจุดหลังแก้ |
| **Secret key จาก env** | Production ต้องตั้ง `SECRET_KEY` ใน environment ไม่ควรใช้ค่า default เดียวกันทุกเครื่อง เพราะ session จะถูก forge ได้ถ้ารู้ key → development อาจใช้ fallback ได้ แต่ production ห้าม |
| **Config จาก env** | `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH` ถ้า hardcode ทำให้เปลี่ยนตาม environment ยาก (เช่น dev ใช้ `./uploads` prod ใช้ `/var/app/uploads`) → ควรดึงจาก env หรือ config file แยกตาม ENV |
| **appeal เก็บ reason/evidence หรือไม่** | ถ้าเก็บ กรรมการจะได้ข้อมูลเพิ่มในการพิจารณา แต่ต้องออกแบบ schema (เก็บที่ RequestRecord หรือตาราง AppealRecord แยก) และแสดงในหน้ารายละเอียดคำขอของ committee → กระทบ UI และสิทธิ์การแสดงผล |
| **appeal_request รองรับอนุมัติบางส่วนหรือไม่** | ปัจจุบัน `/appeal/` เปิดได้เฉพาะคำขอที่ `ไม่อนุมัติ` ทั้งก้อน ส่วน `อนุมัติบางส่วน` ใช้ submit_appeal ใน view_request เลือกงานเป็นรายการ → ถ้าให้ appeal_request รองรับอนุมัติบางส่วนด้วย ต้องตัดสินใจว่า flow จะเหมือนไม่อนุมัติ (form reason+evidence ทั้งคำขอ) หรือให้เลือกงานเหมือน view_request (อาจซ้ำ logic) |

#### สาเหตุที่ต้องแก้ (เทคนิค)

| รายการ | สาเหตุ |
|--------|--------|
| **Connection leak** | ถ้า `conn.execute()` หรือ `conn.commit()` เกิด exception โค้ดจะไม่ถึง `conn.close()` ทำให้ connection ค้างและอาจเกินขีดจำกัดของ SQLite → ต้องใช้ `try/finally` ปิด connection เสมอ |
| **api_check_work_duplicate โหลดทุกคำขอ** | ตอนนี้โหลด `RequestRecord` ทั้งตารางมา deserialize แล้ว loop หา duplicate ชื่อผลงาน ถ้ามีคำขอหลายพันรายการจะช้ามาก → ควร query เฉพาะ `works_json` ที่เกี่ยวข้อง หรือใช้ full-text search / query ใน SQL แทน |
| **Bare except** | `except:` จะจับทุก exception รวมถึง `KeyboardInterrupt`, `SystemExit` ทำให้กด Ctrl+C อาจไม่หยุดหรือซ่อน bug จริง → ควรระบุ `except Exception:` หรือ exception เฉพาะ เช่น `JSONDecodeError`, `ValueError` |
| **deserialize_request ไม่ handle invalid JSON** | ถ้ามีคนแก้ DB ตรงๆ หรือ migration ผิดพลาดทำให้ `works_json` เสีย `json.loads()` จะโยน `JSONDecodeError` และทำให้ view_request crash → ควร try/except แล้วคืนค่า default หรือแสดง error ที่เป็นมิตร |
| **Magic strings สถานะ** | สถานะเช่น `'แบบร่าง'`, `'ส่งแล้ว'` ใช้ซ้ำในหลายไฟล์ ถ้าพิมพ์ผิดจะไม่ error ทันที ทำให้ bug หายาก → ย้ายไป constants เช่น `STATUS_DRAFT = 'แบบร่าง'` แล้ว import ใช้ จะลด typo และ refactor ง่ายขึ้น |

