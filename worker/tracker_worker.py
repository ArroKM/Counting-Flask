import os
import sys
import json
import asyncio
import signal
import logging
import platform
from dotenv import load_dotenv
from models.models import ZoneData, get_session
from lib.api_tracker import AsyncApiTracker

# Load path dan .env
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tracker_worker")

# Konfigurasi zona
ZONES = [
    {"name": "hijau", "in_env": "IN_DEVICES_HIJAU", "out_env": "OUT_DEVICES_HIJAU", "interval_env": "INTERVAL_HIJAU_SEC"},
    {"name": "merah", "in_env": "IN_DEVICES_MERAH", "out_env": "OUT_DEVICES_MERAH", "interval_env": "INTERVAL_MERAH_SEC"},
]


async def fetch_and_store(zone: str, in_devices: list[str], out_devices: list[str]):
    try:
        log.info("[%s] 🔄 Fetching data ...", zone.upper())
        tracker = AsyncApiTracker(in_devices=in_devices, out_devices=out_devices)
        data = await asyncio.wait_for(tracker.run(), timeout=120)

        # Cek validitas data
        if not isinstance(data, dict):
            log.warning("[%s] ⚠️ Data tidak valid, skip simpan", zone.upper())
            return
        if data.get("offline"):
            log.warning("[%s] ⚠️ API offline, skip simpan", zone.upper())
            return

        with get_session() as session:
            session.query(ZoneData).filter(ZoneData.zone == zone).delete()
            session.add(ZoneData(zone=zone, data=json.dumps(data, default=str)))
            session.commit()

        log.info("[%s] ✅ Saved (in: %d, out: %d, cur: %d)", zone.upper(), data['totalin'], data['totalout'], data['totalcur'])

    except asyncio.TimeoutError:
        log.warning("[%s] ⏱️ Timeout saat fetch data", zone.upper())
    except Exception:
        log.exception("[%s] ❌ Gagal menyimpan data", zone.upper())


async def zone_loop(zone_cfg: dict):
    name = zone_cfg["name"]
    in_devices = [d.strip() for d in os.getenv(zone_cfg["in_env"], "").split(",") if d.strip()]
    out_devices = [d.strip() for d in os.getenv(zone_cfg["out_env"], "").split(",") if d.strip()]
    interval = int(os.getenv(zone_cfg["interval_env"], "30"))

    if not in_devices or not out_devices:
        log.warning("[%s] ❌ IN/OUT devices belum disetel di .env", name.upper())
        return

    log.info("[%s] 🟢 Worker berjalan setiap %ds", name.upper(), interval)

    while True:
        await fetch_and_store(name, in_devices, out_devices)
        await asyncio.sleep(interval)


async def run_worker():
    log.info("[Worker] 🟢 Async tracker worker dimulai...")
    await asyncio.gather(*(zone_loop(zone) for zone in ZONES))


def setup_graceful_shutdown(loop: asyncio.AbstractEventLoop):
    async def shutdown():
        log.info("[Worker] 🛑 Sedang shutdown...")
        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()
        log.info("[Worker] ✅ Shutdown selesai")

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            pass  # Windows fallback


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    setup_graceful_shutdown(loop)

    try:
        loop.run_until_complete(run_worker())
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("[Worker] 🚪 Keluar dari loop")
    finally:
        loop.close()
        log.info("[Worker] ✅ Loop closed cleanly")