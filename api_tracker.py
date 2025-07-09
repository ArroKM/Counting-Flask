import datetime
import requests
import psycopg2
import os

class ApiTracker:
    def __init__(self, in_devices=None, out_devices=None):
        self.in_devices = in_devices or []
        self.out_devices = out_devices or []

        self.api_url = os.getenv("API_URL")
        self.access_token = os.getenv("ACCESS_TOKEN")

        self.db_host = os.getenv("DB_HOST")
        self.db_port = os.getenv("DB_PORT")
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_pass = os.getenv("DB_PASS")
        self.conn = psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_pass
        )

        self.api_offline = False  # ⬅️ untuk flag status API

    def run(self):
        page = 1
        events = []

        while True:
            data = self.fetch_page(page)
            if data is None:
                self.api_offline = True
                break
            if not data:
                break
            events.extend(data)
            page += 1

        if self.api_offline:
            return {
                'offline': True,
                'totalin': 0,
                'totalout': 0,
                'totalcur': 0,
                'data': []
            }

        per_person = {}
        departments = {}

        for e in events:
            dept = e.get('deptName', '')
            pin = e.get('pin', '')
            dev = e.get('devName', '')
            time = e.get('eventTime', '')
            name = e.get('name', '')
            event_name = e.get('eventName', '')

            if not all([dept, pin, dev, time]) or event_name in ['Global Anti-Passback(logical)', 'Disconnected']:
                continue

            ts = int(datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S").timestamp())
            event_type = self.get_type_from_device(dev)
            if not event_type:
                continue

            if pin not in per_person:
                per_person[pin] = {
                    'dept': dept,
                    'status': 'outside',
                    'last': {'in': 0, 'out': 0},
                    'events': [],
                    'name': name,
                    'last_time': ''
                }

            if abs(ts - per_person[pin]['last'][event_type]) <= 60:
                continue

            per_person[pin]['last'][event_type] = ts

            if event_type == 'in' and per_person[pin]['status'] == 'outside':
                per_person[pin]['status'] = 'inside'
                per_person[pin]['events'].append({'type': 'in', 'ts': ts, 'time': time})
                per_person[pin]['last_time'] = time
            elif event_type == 'out' and per_person[pin]['status'] == 'inside':
                per_person[pin]['status'] = 'outside'
                per_person[pin]['events'].append({'type': 'out', 'ts': ts, 'time': time})
                per_person[pin]['last_time'] = time

        summary = {
            'offline': False,
            'totalin': 0,
            'totalout': 0,
            'totalcur': 0,
            'data': []
        }

        for pin, data in per_person.items():
            dept = data['dept']
            if dept not in departments:
                departments[dept] = {
                    'dept': dept,
                    'in': 0,
                    'out': 0,
                    'cur': 0,
                    'person': {'data': []}
                }

            in_count = len([e for e in data['events'] if e['type'] == 'in'])
            out_count = len([e for e in data['events'] if e['type'] == 'out'])

            summary['totalin'] += in_count
            summary['totalout'] += out_count
            departments[dept]['in'] += in_count
            departments[dept]['out'] += out_count

            if data['status'] == 'inside':
                summary['totalcur'] += 1
                departments[dept]['cur'] += 1
                detail = self.get_person_detail(pin, data['last_time'], data['name'])
                if detail:
                    departments[dept]['person']['data'].append(detail)

        summary['data'] = list(departments.values())
        return summary

    def get_type_from_device(self, dev_name):
        dev_name = dev_name.strip().lower()
        in_devs = [d.strip().lower() for d in self.in_devices]
        out_devs = [d.strip().lower() for d in self.out_devices]

        if dev_name in in_devs:
            return 'in'
        if dev_name in out_devs:
            return 'out'
        return None

    def fetch_page(self, page):
        today = datetime.datetime.now().strftime('%y-%m-%d')
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%y-%m-%d')
        url = f"{self.api_url}?endDate=20{tomorrow}%2023%3A59%3A59&pageNo={page}&pageSize=800&startDate=20{today}%2000%3A00%3A00&access_token={self.access_token}"

        try:
            response = requests.get(url, verify=False, timeout=60)
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception:
            return None  # ⬅️ Kembalikan None jika error

    def get_person_detail(self, pin, last_time, name):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM pers_person WHERE pin = %s", (pin,))
            res = cur.fetchone()
            if not res:
                return {}

            cur.execute("SELECT * FROM pers_attribute_ext WHERE person_id = %s", (res[0],))
            re = cur.fetchone()

            cur.execute("SELECT * FROM park_person WHERE pers_person_pin = %s", (pin,))
            ress = cur.fetchone()
            carplat = ''
            if ress:
                cur.execute("SELECT * FROM park_car_number WHERE id = %s", (ress[0],))
                car = cur.fetchone()
                if car:
                    carplat = car[14] if len(car) > 14 else ''

            gender = 'Male' if res[19] == 'M' else 'Female' if res[19] == 'F' else ''

            return {
                "name": name or '',
                "id": pin,
                "time": last_time,
                "gender": gender,
                "email": res[16] or '',
                "phone": res[26] or '',
                "plat": carplat,
                "birthday": res[13] or '',
                "nipeg": re[19] if re else ''
            }