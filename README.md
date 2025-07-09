Taruh folder counting di C:

RUNNING APP:

install python 3.13 ada di folder PY
jangan lupa centang “Add Python to PATH”

install requirements.txt
- python -m venv venv
- pip install -r requirements.txt

Masuk Ke Folde nssm-2.24
masuk ke CMD ketik (nssm install FlaskApp)

lalu setting:
- path : C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe
- Startup directory : Arahkan ke root folder aplikasi (counting)
- Arguments : app.py

jika sudah klik okee

untuk menjalankan nya : nssm start FlaskApp
Untuk menghentikannya : nssm stop FlaskApp

Endpoint:
- / (zona hijau)
- /merah (zona merah)
- /api/data (API untuk zona hijau)
- /api/merah (API untuk zona merah)
- /register (Untuk registrasi / weblink)


*CATATAN
Untuk semua data yang di butuhkan (access token, url, in device, out device, zona hijau, zona merah, regis) ada di file .env tinggal sesuaikan aja