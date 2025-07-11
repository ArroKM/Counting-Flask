import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import schedule
import time
from dotenv import load_dotenv
from models.models import ZoneData, get_session

from lib.api_tracker import ApiTracker  # pastikan file ini ada dan tidak diubah

load_dotenv()

def fetch_and_store(zone, in_env, out_env):
    try:
        print(f"[{zone.upper()}] Fetching data...")

        in_dev = [x.strip() for x in os.getenv(in_env, "").split(",") if x.strip()]
        out_dev = [x.strip() for x in os.getenv(out_env, "").split(",") if x.strip()]

        tracker = ApiTracker(in_devices=in_dev, out_devices=out_dev)
        data = tracker.run()

        session = get_session()

        # Hapus data lama untuk zona ini
        session.query(ZoneData).filter(ZoneData.zone == zone).delete()

        # Simpan data baru (gunakan default=str untuk hindari error date)
        session.add(ZoneData(zone=zone, data=json.dumps(data, default=str)))
        session.commit()
        session.close()

        print(f"[{zone.upper()}] ✅ Data saved successfully.")
    except Exception as e:
        print(f"[{zone.upper()}] ❌ Failed to save data: {e}")

def run_worker():
    # Jadwal update data untuk masing-masing zona
    schedule.every(30).seconds.do(fetch_and_store, zone="hijau", in_env="IN_DEVICES_HIJAU", out_env="OUT_DEVICES_HIJAU")
    schedule.every(30).seconds.do(fetch_and_store, zone="merah", in_env="IN_DEVICES_MERAH", out_env="OUT_DEVICES_MERAH")

    print("[Worker] Running... (press Ctrl+C to stop)")
    while True:
        schedule.run_pending()
        time.sleep(1)
