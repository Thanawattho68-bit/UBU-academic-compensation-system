import json
import random
from datetime import datetime, timedelta

def generate_mock_requests(count=50):
    with open('backup/users.json', 'r', encoding='utf-8') as f:
        users = json.load(f)
    
    # Filter only applicants
    applicants = [u for u in users if u['role'] == 'applicant']
    
    statuses = ['ส่งแล้ว', 'อนุมัติ', 'ไม่อนุมัติ', 'รอการพิจารณา', 'แก้ไข']
    fiscal_years = ['2568', '2569']
    
    requests = []
    
    for i in range(count):
        user = random.choice(applicants)
        status = random.choice(statuses)
        fiscal_year = random.choice(fiscal_years)
        
        # Generate some scores
        score = random.uniform(5.0, 50.0)
        approved_amount = 0
        if status == 'อนุมัติ':
            approved_amount = random.uniform(5000, 50000)
            
        now = datetime.now() - timedelta(days=random.randint(0, 365))
        date_str = now.strftime('%d/%m/%Y %H:%M')
        
        req_id = f"MOCK-REQ-{2569 if fiscal_year == '2569' else 2568}{i:03d}"
        
        # Determine pos category for mock stats
        pos = user.get('academic_position', [])
        if isinstance(pos, str): pos = [pos]
        
        req = {
            "id": req_id,
            "applicant": user['username'],
            "applicant_name": user['name'],
            "fiscal_year": fiscal_year,
            "status": status,
            "date": date_str,
            "score": round(score, 3),
            "approved_amount": round(approved_amount, 2),
            "timeline_status": "ontime",
            "batch_id": None,
            "applicant_info": {
                "title_name": user.get('title_name'),
                "academic_position": user.get('academic_position'),
                "department": user.get('department'),
                "faculty": user.get('faculty')
            },
            "works": [
                {
                    "title": f"Mock Work Title {i}",
                    "type": "research",
                    "status": "อนุมัติ" if status == 'อนุมัติ' else 'ส่งแล้ว',
                    "score_calc": round(score, 3),
                    "payment_calc": round(approved_amount, 2)
                }
            ]
        }
        requests.append(req)
        
    with open('backup/requests.json', 'w', encoding='utf-8') as f:
        json.dump(requests, f, ensure_ascii=False, indent=4)
    
    print(f"✅ Generated {count} mock requests in backup/requests.json")

if __name__ == "__main__":
    generate_mock_requests(50)
