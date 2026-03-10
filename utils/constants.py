"""
utils/constants.py
ค่าคงที่สถานะและบทบาทที่ใช้ร่วมกันทั้งระบบ
"""

# สถานะคำขอ (Request)
STATUS_DRAFT = 'แบบร่าง'
STATUS_SUBMITTED = 'ส่งแล้ว'
STATUS_EDIT = 'แก้ไข'
STATUS_WAIT_HISTORY = 'รอตรวจประวัติการยื่นขอ'
STATUS_WORKS_PASS = 'ผลงานผ่าน'
STATUS_WORKS_DUP = 'ผลงานซ้ำซ้อน'
STATUS_DUP_PARTIAL = 'ซ้ำซ้อนบางส่วน'
STATUS_WAIT_COMMITTEE = 'รอเสนอพิจารณา'
STATUS_IN_REVIEW = 'อยู่ในรอบพิจารณา'
STATUS_PENDING = 'รอการพิจารณา'
STATUS_APPEAL = 'รอการอุทธรณ์'
STATUS_APPROVED = 'อนุมัติ'
STATUS_REJECTED = 'ไม่อนุมัติ'
STATUS_APPROVED_PARTIAL = 'อนุมัติบางส่วน'
STATUS_PUBLISHED = 'ประกาศผลแล้ว'

# สถานะที่ผู้ยื่นสามารถยกเลิกได้
CANCELLABLE_STATUSES = [
    STATUS_DRAFT, STATUS_SUBMITTED, STATUS_EDIT,
    STATUS_WAIT_HISTORY, STATUS_WORKS_PASS, STATUS_WAIT_COMMITTEE, STATUS_PENDING
]

# สถานะงาน (Work)
WORK_APPROVED = 'อนุมัติ'
WORK_REJECTED = 'ไม่อนุมัติ'
WORK_DUP = 'ผลงานซ้ำซ้อน'
WORK_PASS = 'ผลงานผ่าน'
WORK_APPEAL = 'รอการอุทธรณ์'

# บทบาท
ROLE_APPLICANT = 'applicant'
ROLE_ADMIN = 'administration'
ROLE_RESEARCH = 'research'
ROLE_COMMITTEE = 'committee'
ROLE_ADMIN_SYS = 'admin'
