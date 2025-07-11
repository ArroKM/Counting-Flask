import os
import sys
import time
import json
import base64
import hashlib
import logging
import threading
import asyncio
import requests
import urllib3
import webbrowser
import socket

from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from waitress import serve
from dotenv import load_dotenv

from models.models import get_session, ZoneData, create_tables
from worker.tracker_worker import run_worker
from blacklist.blacklist_tracker import BlacklistTracker

# === Setup ===
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()
create_tables()

# === Logging ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/app.log", level=logging.INFO)
log = logging.getLogger("app")
log.info("Flask app dimulai...")

# === Flask ===
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# === Upload ===
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# === Env Vars ===
base_url = os.getenv("URL_DEPT")
add_url = os.getenv("URL_ADD_PERSON")
access_token = os.getenv("ACCESS_TOKEN")
title_hijau = os.getenv("TITLE_HIJAU", "MONITORING ZONA HIJAU")
title_merah = os.getenv("TITLE_HIJAU", "MONITORING ZONA MERAH")

# === Utilities ===
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_departments():
    headers = {"Accept": "application/json"}
    departments = {}

    for i in range(1, 30):
        try:
            url = f"{base_url}{i}?access_token={access_token}"
            resp = requests.get(url, headers=headers, verify=False, timeout=3)
            data = resp.json()

            if data.get("code") == 0 and "data" in data:
                dept = data["data"]
                departments[dept["code"]] = dept["name"]
        except Exception as e:
            log.warning(f"[Dept API] Error get dept {i}: {e}")
            continue

    return departments if departments else None

def get_zone_data(zone: str):
    try:
        session = get_session()
        record = session.query(ZoneData).filter(ZoneData.zone == zone).first()
        session.close()
        return json.loads(record.data) if record else {"offline": True}
    except Exception as e:
        log.error(f"[ZoneData] Gagal load zone {zone}: {e}")
        return {"offline": True, "error": str(e)}

# === Routes ===
@app.route("/")
def zona_hijau():
    return render_template("index.html", title=title_hijau, zone="hijau")

@app.route("/merah")
def zona_merah():
    return render_template("index.html", title=title_merah, zone="merah")

@app.route("/api/data")
def api_data():
    return jsonify(get_zone_data("hijau"))

@app.route("/api/merah")
def api_merah():
    return jsonify(get_zone_data("merah"))

@app.route("/api/blacklist")
def api_blacklist():
    return jsonify(BlacklistTracker().run())

@app.route("/register", methods=["GET", "POST"])
def register():
    departments = get_departments()
    if departments is None:
        return render_template("register.html", title="Registration - Indonesia Power", offline=True)

    if request.method == "POST":
        name = request.form.get("name", "").strip().upper()
        nip = request.form.get("nip", "").strip().upper()
        dept = request.form.get("dept", "").strip().upper()
        plat = request.form.get("plat", "").strip().upper()
        gender = request.form.get("gender", "M")

        file = request.files.get("filename")
        if not file or not allowed_file(file.filename):
            flash("File tidak valid. Harus .jpg atau .png", "danger")
            return redirect(url_for("register"))

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        with open(filepath, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        pin = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

        payload = {
            "name": name,
            "pin": pin,
            "deptCode": dept,
            "gender": gender,
            "carPlate": plat,
            "personPhoto": encoded_image,
            "accLevelIds": "1",
            "certType": 2,
            "ssn": "111111",
            "cardNo": "",
            "certNumber": "",
            "accStartTime": "",
            "accEndTime": "",
            "email": "",
            "lastName": "",
            "personPwd": "",
            "mobilePhone": "",
            "hireDate": "",
            "birthday": "",
            "supplyCards": "",
            "isDisabled": False,
            "isSendMail": False
        }

        try:
            url = f"{add_url}?access_token={access_token}"
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
            result = response.json()

            if result.get("message") == "success":
                flash("Registrasi berhasil!", "success")
            else:
                msg = result.get("message", "Unknown error")
                flash(f"Gagal registrasi: {msg}", "danger")
        except Exception as e:
            flash("Gagal menghubungi API pendaftaran", "danger")
            log.error(f"[Register] Error: {e}")

        return redirect(url_for("register"))

    return render_template("register.html", title="Registration - Indonesia Power", departments=departments, offline=False)

# === Background Worker ===
def start_worker_once():
    try:
        log.info("[Worker] Menjalankan tracker worker...")
        threading.Thread(target=lambda: asyncio.run(run_worker()), daemon=True).start()
    except Exception as e:
        log.exception("[Worker] Gagal menjalankan tracker:")

# === Single Instance Lock ===
CONTROL_PORT = 59781

def ensure_single_instance_and_open_browser():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', CONTROL_PORT))
        sock.listen(1)

        def listen_and_open_browser():
            while True:
                conn, _ = sock.accept()
                with conn:
                    port = int(os.getenv("APP_PORT", 12345))
                    webbrowser.open_new_tab(f"http://localhost:{port}")

        threading.Thread(target=listen_and_open_browser, daemon=True).start()

    except OSError:
        try:
            with socket.create_connection(("localhost", CONTROL_PORT), timeout=1) as s:
                s.send(b"open")
        except Exception:
            pass
        sys.exit(0)

# === Entry Point ===
if __name__ == "__main__":
    ensure_single_instance_and_open_browser()

    with open("app.pid", "w") as f:
        f.write(str(os.getpid()))
    port = int(os.getenv("APP_PORT", 12345))

    webbrowser.open_new_tab(f"http://localhost:{port}")
    start_worker_once()
    serve(app, host="0.0.0.0", port=port)