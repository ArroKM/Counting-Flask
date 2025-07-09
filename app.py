import urllib3
from waitress import serve
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from blacklist_tracker import BlacklistTracker
from api_tracker import ApiTracker
import time, hashlib
import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "supersecret"  # For flash messages

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
base_url = os.getenv("URL_DEPT")
add_url = os.getenv("URL_ADD_PERSON")
access_token = os.getenv("ACCESS_TOKEN")

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

def get_device_list(env_name):
    return [x.strip() for x in os.getenv(env_name, "").split(",") if x.strip()]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def zona_hijau():
    in_dev = get_device_list("IN_DEVICES_HIJAU")
    out_dev = get_device_list("OUT_DEVICES_HIJAU")
    tracker = ApiTracker(in_devices=in_dev, out_devices=out_dev)
    data = tracker.run()
    return render_template("index.html", data=data, title="COUNTING PEOPLE ZONA HIJAU", zone="hijau")


@app.route("/merah", methods=["GET"])
def zona_merah():
    in_dev_merah = get_device_list("IN_DEVICES_MERAH")
    out_dev_merah = get_device_list("OUT_DEVICES_MERAH")
    tracker = ApiTracker(in_devices=in_dev_merah, out_devices=out_dev_merah)
    data = tracker.run()
    return render_template("index.html", data=data, title="COUNTING PEOPLE ZONA MERAH", zone="merah")


@app.route("/api/data", methods=["GET"])
def api_data():
    in_dev = get_device_list("IN_DEVICES_HIJAU")
    out_dev = get_device_list("OUT_DEVICES_HIJAU")
    tracker = ApiTracker(in_devices=in_dev, out_devices=out_dev)
    return jsonify(tracker.run())


@app.route("/api/merah", methods=["GET"])
def api_merah():
    in_dev = get_device_list("IN_DEVICES_MERAH")
    out_dev = get_device_list("OUT_DEVICES_MERAH")
    tracker = ApiTracker(in_devices=in_dev, out_devices=out_dev)
    return jsonify(tracker.run())


@app.route('/api/blacklist', methods=['GET'])
def get_blacklist():
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


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5050)
