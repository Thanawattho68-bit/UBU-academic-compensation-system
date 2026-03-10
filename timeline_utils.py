"""Helper สำหรับ timeline message (ถ้าใช้กับ JSON-based config) - ปัจจุบันระบบใช้ DB"""
from datetime import datetime
from utils import load_config, get_current_fiscal_year, parse_thai_date


def get_timeline_message(timeline=None):
    if not timeline:
        timelines, fy = load_config('timeline.json', []), get_current_fiscal_year()
        timeline = next((t for t in timelines if str(t.get('fiscal_year')) == str(fy)), timelines[0] if timelines else {}) if isinstance(timelines, list) else timelines

    if not timeline: return ""
    
    now_date = datetime.now().date()
    for r in [r for r in timeline.get('rounds', []) if r.get('type') == 'consideration']:
        try:
            s_dt, e_dt = parse_thai_date(r['start_date']), parse_thai_date(r['end_date'])
            if s_dt and e_dt and s_dt.date() <= now_date <= e_dt.date():
                return f"ขออภัย! ขณะนี้อยู่ในช่วง {r.get('name', 'รอบพิจารณา')} ({r['start_date']} - {r['end_date']})\\nระบบจึงปิดการรับคำขอชั่วคราว"
        except (KeyError, TypeError):
            pass

    return f"ขออภัย! ขณะนี้ระบบปิดการรับคำขอ\\nจะเปิดรับคำขออีกครั้งในวันที่ {timeline.get('start_date', '1/10')} ของรอบปีงบประมาณถัดไป"
