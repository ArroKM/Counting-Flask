import datetime
import requests
import psycopg2
import os
from dotenv import load_dotenv

# Path absolut ke folder root (di mana .env berada)
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)

class ApiTracker:
    """
    ApiTracker digunakan untuk mengambil dan memproses data kehadiran dari API eksternal
    serta menyusun rekapitulasi berdasarkan departemen dan individu yang masih berada di dalam lokasi.
    """

    def __init__(self, in_devices=None, out_devices=None):
        # Konfigurasi perangkat in/out
        self.in_devices = set(d.strip().lower() for d in (in_devices or []))
        self.out_devices = set(d.strip().lower() for d in (out_devices or []))

        # Konfigurasi API dan database
        self.api_url = os.getenv("API_URL")
        self.access_token = os.getenv("ACCESS_TOKEN")
        self.db_host = os.getenv("DB_HOST")
        self.db_port = os.getenv("DB_PORT")
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_pass = os.getenv("DB_PASS")

        # Koneksi ke database
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_pass
            )
        except Exception as e:
            print(f"[ERROR] Gagal koneksi ke database: {e}")
            self.conn = None

        self.api_offline = False
        self.person_cache = {}

    def __del__(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

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

            try:
                ts = int(datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S").timestamp())
            except ValueError:
                continue

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

            # Filter double event dalam 60 detik
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

            in_count = sum(1 for e in data['events'] if e['type'] == 'in')
            out_count = sum(1 for e in data['events'] if e['type'] == 'out')

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
        if dev_name in self.in_devices:
            return 'in'
        if dev_name in self.out_devices:
            return 'out'
        return None

    def fetch_page(self, page):
        today = datetime.datetime.now().strftime('%y-%m-%d')
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%y-%m-%d')
        url = (
            f"{self.api_url}"
            f"?endDate=20{tomorrow}%2023%3A59%3A59"
            f"&pageNo={page}"
            f"&pageSize=800"
            f"&startDate=20{today}%2000%3A00%3A00"
            f"&access_token={self.access_token}"
        )

        try:
            response = requests.get(url, verify=False, timeout=60)
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            print(f"[ERROR] Gagal mengambil data API di halaman {page}: {e}")
            return None

    def get_person_detail(self, pin, last_time, name):
        if not self.conn:
            return {}

        if pin in self.person_cache:
            detail = self.person_cache[pin].copy()
            detail['time'] = last_time
            detail['name'] = name or detail['name']
            return detail

        try:
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

                detail = {
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

                self.person_cache[pin] = detail.copy()
                return detail

        except Exception as e:
            print(f"[ERROR] get_person_detail gagal untuk pin {pin}: {e}")
            return {}