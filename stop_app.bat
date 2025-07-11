@echo off
echo [STOP] Membaca PID dari app.pid...

if not exist app.pid (
    echo [ERROR] File PID tidak ditemukan.
    timeout /t 5 >nul
    exit /b 1
)

set /p PID=<app.pid
echo [KILL] Menutup proses dengan PID: %PID%...
taskkill /PID %PID% /F >nul 2>&1

if %ERRORLEVEL%==0 (
    echo [DONE] Proses berhasil dihentikan.
    del app.pid
) else (
    echo [ERROR] Gagal menghentikan proses. Mungkin proses sudah tidak aktif.
)

echo Menutup dalam 5 detik...
timeout /t 5 >nul
exit
