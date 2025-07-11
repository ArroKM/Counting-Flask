Taruh folder counting di C:

RUNNING APP:

install python 3.13 ada di folder PY
jangan lupa centang “Add Python to PATH”

install requirements.txt
- pip install --no-index --find-links=offline_packages -r requirements.txt

# Start servicenya
Klik 2x start_app.bat

# Untuk stop
Klik 2x stop_app.bat

# Untuk restart
Klik 2x restart_app.bat


Endpoint:
- / (zona hijau)
- /merah (zona merah)
- /api/data (API untuk zona hijau)
- /api/merah (API untuk zona merah)
- /register (Untuk registrasi / weblink)


*CATATAN
Untuk semua data yang di butuhkan (access token, url, in device, out device, zona hijau, zona merah, regis) ada di file .env tinggal sesuaikan aja

Jika mau gunakan file exe nya cukup ekstrak file flask-exe.zip lalu update .env nya dan jalankan file counting.exe