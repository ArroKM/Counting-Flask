import os
import threading
import time
import json
import logging
import base64
import hashlib
import requests
import urllib3
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from models.models import get_session, ZoneData, create_tables
from worker.tracker_worker import run_worker
from blacklist.blacklist_tracker import BlacklistTracker
from waitress import serve

# ===== Save PID =====
with open("app.pid", "w") as f:
    f.write(str(os.getpid()))

# ===== Logging Setup =====
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/app.log", level=logging.INFO)
logging.info("Flask app dimulai...")

# ===== Load .env =====
load_dotenv()

# ===== Create DB Tables =====
create_tables()

# ===== Flask Setup =====
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "supersecret"

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# ===== Environment Vars =====
base_url = os.getenv("URL_DEPT")
add_url = os.getenv("URL_ADD_PERSON")
access_token = os.getenv("ACCESS_TOKEN")

# ===== Helper Functions =====
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_departments():
    headers = {"Accept": "application/json"}
    departments = {}
    for i in range(1, 30):
        try:
            url = f"{base_url}{i}?access_token={access_token}"
            response = requests.get(url, headers=headers, verify=False, timeout=3)
            data = response.json()
            if data.get("code") == 0 and "data" in data:
                dept_code = data["data"]["code"]
                dept_name = data["data"]["name"]
                departments[dept_code] = dept_name
        except Exception:
            continue
    return departments if departments else None

def get_zone_data(zone):
    try:
        session = get_session()
        record = session.query(ZoneData).filter(ZoneData.zone == zone).first()
        session.close()
        return json.loads(record.data) if record else {"offline": True}
    except Exception as e:
        return {"offline": True, "error": str(e)}

# ===== Routes =====
@app.route("/")
def zona_hijau():
    return render_template("index.html", title="MONITORING ZONA HIJAU", zone="hijau")

@app.route("/merah")
def zona_merah():
    return render_template("index.html", title="MONITORING ZONA MERAH", zone="merah")

@app.route("/api/data")
def api_data():
    data = get_zone_data("hijau")
    return jsonify(data)

@app.route("/api/merah")
def api_merah():
    data = get_zone_data("merah")
    return jsonify(data)

@app.route("/api/blacklist")
def api_blacklist():
    tracker = BlacklistTracker()
    data = tracker.run()
    return jsonify(data)

@app.route("/register", methods=["GET", "POST"])
def register():
    departments = get_departments()
    if departments is None:
        return render_template("register.html", title="Registration - Indonesia Power", offline=True)

    if request.method == "POST":
        name = request.form.get("name", "").upper()
        nip = request.form.get("nip", "").upper()
        dept = request.form.get("dept", "").upper()
        plat = request.form.get("plat", "").upper()
        gender = request.form.get("gender", "M")

        file = request.files.get("filename")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            with open(file_path, "rb") as f:
                encoded_image = base64.b64encode(f.read()).decode("utf-8")

            pin = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

            payload = {
                "accEndTime": "",
                "accLevelIds": "1",
                "accStartTime": "",
                "birthday": "",
                "carPlate": plat,
                "cardNo": "",
                "certNumber": "",
                "certType": 2,
                "deptCode": dept,
                "email": "",
                "gender": gender,
                "hireDate": "",
                "isDisabled": False,
                "isSendMail": False,
                "lastName": "",
                "mobilePhone": "",
                "name": name,
                "personPhoto": encoded_image,
                "personPwd": "",
                "pin": pin,
                "ssn": "111111",
                "supplyCards": ""
            }

            url = f"{add_url}?access_token={access_token}"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            try:
                response = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
                result = response.json()
                if result.get("message") == "success":
                    flash("Registrasi berhasil!", "success")
                    return redirect(url_for("register"))
                else:
                    flash(f"Gagal registrasi: {result.get('message', 'Unknown error')}", "danger")
            except Exception as e:
                flash("Server sedang offline. Tidak dapat menghubungi API.", "danger")
        else:
            flash("File tidak valid. Harus .jpg atau .png", "danger")

    return render_template("register.html", title="Registration - Indonesia Power", departments=departments, offline=False)

# ===== Start Worker Thread Sekali =====
def start_worker_once():
    try:
        print("[Worker] ✅ Starting tracker scheduler in background thread...")
        threading.Thread(target=run_worker, daemon=True).start()
    except Exception as e:
        print(f"[Worker] ❌ Failed to start scheduler: {e}")

# ===== Entry Point =====
if __name__ == "__main__":
    start_worker_once()
    serve(app, host="0.0.0.0", port=5050)
