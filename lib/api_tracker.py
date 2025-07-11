import os, asyncio, datetime, aiohttp, asyncpg, logging
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

IGNORED_EVENTS = {'Global Anti-Passback(logical)', 'Disconnected'}

class AsyncApiTracker:
    def __init__(self, in_devices=None, out_devices=None):
        self.in_devices = set(map(str.lower, map(str.strip, in_devices or [])))
        self.out_devices = set(map(str.lower, map(str.strip, out_devices or [])))

        self.api_url = os.getenv("API_URL")
        self.access_token = os.getenv("ACCESS_TOKEN")
        self.db_dsn = os.getenv("DATABASE_URL")

        self.api_offline = False
        self.person_cache = {}

    def get_type_from_device(self, dev_name):
        dev = dev_name.strip().lower()
        return 'in' if dev in self.in_devices else 'out' if dev in self.out_devices else None

    @staticmethod
    def timestamp_from_str(time_str):
        try:
            return int(datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").timestamp())
        except Exception:
            return None

    async def fetch_page(self, session, page):
        today = datetime.datetime.now().strftime('%y-%m-%d')
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%y-%m-%d')

        url = (
            f"{self.api_url}?endDate=20{tomorrow}%2023%3A59%3A59"
            f"&pageNo={page}&pageSize=800&startDate=20{today}%2000%3A00%3A00"
            f"&access_token={self.access_token}"
        )

        try:
            async with session.get(url, timeout=60, ssl=False) as resp:
                if resp.status != 200:
                    log.warning(f"[API] Page {page} status {resp.status}")
                    return None
                return (await resp.json()).get("data", [])
        except Exception as e:
            log.error(f"[API] Failed to fetch page {page}: {e}")
            return None

    async def get_person_detail(self, conn, pin, last_time, name):
        if pin in self.person_cache:
            detail = self.person_cache[pin].copy()
            detail["time"] = last_time
            detail["name"] = name or detail["name"]
            return detail

        try:
            person = await conn.fetchrow("SELECT * FROM pers_person WHERE pin = $1", pin)
            if not person:
                return {}

            attr = await conn.fetchrow("SELECT * FROM pers_attribute_ext WHERE person_id = $1", person[0])

            plat = ''
            park = await conn.fetchrow("SELECT * FROM park_person WHERE pers_person_pin = $1", pin)
            if park:
                car = await conn.fetchrow("SELECT * FROM park_car_number WHERE id = $1", park[0])
                plat = car[14] if car and len(car) > 14 and isinstance(car[14], str) else ''

            gender = person[19] if len(person) > 19 and isinstance(person[19], str) else ''
            email = person[16] if len(person) > 16 and isinstance(person[16], str) else ''
            phone = person[26] if len(person) > 26 and isinstance(person[26], str) else ''
            birthday = person[13] if len(person) > 13 and isinstance(person[13], (str, datetime.date)) else ''

            detail = {
                "name": name or '',
                "id": pin,
                "time": last_time,
                "gender": {'M': 'Male', 'F': 'Female'}.get(gender, ''),
                "email": email,
                "phone": phone,
                "plat": plat,
                "birthday": birthday,
                "nipeg": attr[19] if attr and len(attr) > 19 and isinstance(attr[19], str) else ''
            }

            self.person_cache[pin] = detail.copy()
            return detail

        except Exception as e:
            log.error(f"[DB] Error getting detail for {pin}: {e}")
            return {}

    async def gather_events(self):
        events, page = [], 1
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                page_data = await self.fetch_page(session, page)
                if page_data is None:
                    self.api_offline = True
                    break
                if not page_data:
                    break
                events.extend(page_data)
                page += 1

        return events

    async def process_events(self, events):
        per_person = {}

        for e in events:
            dept = e.get("deptName", "").strip()
            pin = e.get("pin", "").strip()
            dev = e.get("devName", "").strip()
            time_str = e.get("eventTime", "").strip()
            name = e.get("name", "").strip()
            event_name = e.get("eventName", "").strip()

            if not all([dept, pin, dev, time_str]):
                continue
            if event_name in IGNORED_EVENTS:
                continue

            ts = self.timestamp_from_str(time_str)
            if not ts:
                continue

            ev_type = self.get_type_from_device(dev)
            if not ev_type:
                continue

            person = per_person.setdefault(pin, {
                'dept': dept,
                'status': 'outside',
                'last': {'in': 0, 'out': 0},
                'events': [],
                'name': name,
                'last_time': ''
            })

            if abs(ts - person['last'][ev_type]) <= 60:
                continue

            person['last'][ev_type] = ts

            if ev_type == 'in' and person['status'] == 'outside':
                person['status'] = 'inside'
                person['events'].append({'type': 'in', 'ts': ts, 'time': time_str})
                person['last_time'] = time_str
            elif ev_type == 'out' and person['status'] == 'inside':
                person['status'] = 'outside'
                person['events'].append({'type': 'out', 'ts': ts, 'time': time_str})
                person['last_time'] = time_str

        return per_person

    async def run(self):
        events = await self.gather_events()
        if self.api_offline:
            return {"offline": True, "totalin": 0, "totalout": 0, "totalcur": 0, "data": []}

        per_person = await self.process_events(events)
        departments = {}
        summary = {"offline": False, "totalin": 0, "totalout": 0, "totalcur": 0, "data": []}

        try:
            async with asyncpg.create_pool(dsn=self.db_dsn) as pool:
                async with pool.acquire() as conn:
                    for pin, data in per_person.items():
                        dept_data = departments.setdefault(data["dept"], {
                            "dept": data["dept"],
                            "in": 0,
                            "out": 0,
                            "cur": 0,
                            "person": {"data": []}
                        })

                        in_count = sum(1 for ev in data["events"] if ev["type"] == "in")
                        out_count = sum(1 for ev in data["events"] if ev["type"] == "out")

                        summary["totalin"] += in_count
                        summary["totalout"] += out_count
                        dept_data["in"] += in_count
                        dept_data["out"] += out_count

                        if data["status"] == "inside":
                            summary["totalcur"] += 1
                            dept_data["cur"] += 1
                            detail = await self.get_person_detail(conn, pin, data["last_time"], data["name"])
                            if detail:
                                dept_data["person"]["data"].append(detail)

            summary["data"] = list(departments.values())
            return summary

        except Exception as e:
            log.critical(f"[DB_POOL] Failed to process data: {e}")
            return {"offline": True, "totalin": 0, "totalout": 0, "totalcur": 0, "data": []}