
def get_timeline_message(timeline=None):
    if not timeline:
        timelines = load_config('timeline.json', [])
        current_fy = get_current_fiscal_year()
        if isinstance(timelines, list):
            timeline = next((t for t in timelines if str(t.get('fiscal_year')) == str(current_fy)), None)
        else:
            timeline = timelines

    if not timeline:
        return "" 
    
    # If open, no alert needed
    # But this function is seemingly called only when we WANT an alert?
    # No, let's make it general.
    # Actually, we only show alert if !can_submit.
    
    # Check if we are in a CONSIDERATION round
    if 'rounds' in timeline and isinstance(timeline['rounds'], list):
        cid_rounds = [r for r in timeline['rounds'] if r.get('type') == 'consideration']
        try:
            now = datetime.now()
            current_date_obj = now.date()
            current_val = now.month * 100 + now.day

            for r in cid_rounds:
                s_date_str = r['start_date']
                e_date_str = r['end_date']
                name = r.get('name', 'รอบพิจารณา')
                
                in_round = False
                 # Check Full Date
                if s_date_str.count('/') == 2 and e_date_str.count('/') == 2:
                        s_dt = parse_thai_date(s_date_str)
                        e_dt = parse_thai_date(e_date_str)
                        if s_dt and e_dt and s_dt.date() <= current_date_obj <= e_dt.date():
                            in_round = True
                else:
                    # Legacy
                     start_d, start_m = map(int, s_date_str.split('/'))
                     end_d, end_m = map(int, e_date_str.split('/'))
                     s_val = start_m * 100 + start_d
                     e_val = end_m * 100 + end_d
                     if s_val <= e_val:
                         if s_val <= current_val <= e_val: in_round = True
                     else:
                         if current_val >= s_val or current_val <= e_val: in_round = True
                
                if in_round:
                    return f"ขออภัย! ขณะนี้อยู่ในช่วง {name} ({s_date_str} - {e_date_str})\\nระบบจึงปิดการรับคำขอชั่วคราว"
        except: pass

    # Default Closed Message
    start_date = timeline.get('start_date', '1/10')
    return f"ขออภัย! ขณะนี้ระบบปิดการรับคำขอ\\nจะเปิดรับคำขออีกครั้งในวันที่ {start_date} ของรอบปีงบประมาณถัดไป"
