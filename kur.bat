@echo off
rem ============================================================
rem  BT Sinifi Sanal Numarator - Windows kurulum betigi
rem
rem  Kullanim:
rem    kur.bat            kur, otomatik baslatmayi ac ve simdi baslat (port 8765)
rem    kur.bat 9000       farkli port ile kur
rem    kur.bat /kaldir    kaldir
rem
rem  Yonetici olmak gerekmez. Ogrencilerin kullandigi Windows hesabiyla calistir.
rem  (Dosya ASCII yazildi: Turkce karakter sorunu cikmasin diye.)
rem ============================================================
setlocal EnableExtensions
title BT Sinifi Numarator - Kurulum
cd /d "%~dp0"

set "PORT=8765"
set "HEDEF_DIZIN=%LOCALAPPDATA%\BTNumarator"
set "HEDEF=%HEDEF_DIZIN%\numarator.py"

if /i "%~1"=="/kaldir" goto kaldir
if /i "%~1"=="--kaldir" goto kaldir
if not "%~1"=="" set "PORT=%~1"

echo %PORT%| findstr /r /c:"^[0-9][0-9][0-9][0-9]$" /c:"^[0-9][0-9][0-9][0-9][0-9]$" >nul
if errorlevel 1 goto port_hata
if %PORT% LSS 1024 goto port_hata
if %PORT% GTR 65535 goto port_hata

echo.
echo === BT Sinifi Sanal Numarator - Kurulum ===
echo.

if not exist "%~dp0numarator.py" (
  echo HATA: numarator.py bu dosyayla ayni klasorde olmali.
  echo ZIP indirdiysen once "Tumunu ayikla" ile klasore cikar.
  goto bitis_hata
)

rem --- Python 3.8+ (tkinter dahil) ara ---
set "PYCMD="
set "PYWCMD="
py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=py -3"
  set "PYWCMD=pyw -3"
  goto python_tamam
)
python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=python"
  set "PYWCMD=pythonw"
  goto python_tamam
)

echo Python 3.8 veya ustu (tkinter dahil) bulunamadi.
where winget >nul 2>&1
if errorlevel 1 goto python_elle
echo Python winget ile kuruluyor, birkac dakika surebilir...
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto python_elle
echo.
echo Python kuruldu. Bu pencereyi kapatip kur.bat dosyasini TEKRAR calistir.
goto bitis

:python_elle
echo.
echo Python'u elle kur: https://www.python.org/downloads/windows/
echo Kurulumda "Add python.exe to PATH" kutusunu isaretle ve "tcl/tk" secili kalsin.
echo Sonra kur.bat dosyasini tekrar calistir.
start "" "https://www.python.org/downloads/windows/"
goto bitis_hata

:python_tamam
echo [1/4] Python bulundu: %PYCMD%

echo [2/4] Dosyalar kopyalaniyor: %HEDEF_DIZIN%
call :durdur
if not exist "%HEDEF_DIZIN%" mkdir "%HEDEF_DIZIN%"
if /i not "%~dp0"=="%HEDEF_DIZIN%\" (
  copy /y "%~dp0numarator.py" "%HEDEF%" >nul
  if errorlevel 1 (
    echo HATA: Dosya kopyalanamadi.
    goto bitis_hata
  )
)

echo [3/4] Bilgisayar acilinca otomatik baslatma ayarlaniyor...
%PYCMD% "%HEDEF%" --kur --port %PORT%
if errorlevel 1 echo UYARI: Otomatik baslatma ayarlanamadi.

echo [4/4] Numarator baslatiliyor...
start "" %PYWCMD% "%HEDEF%" --port %PORT%

rem --- Guvenlik duvari (panele diger bilgisayarlardan girebilmek icin) ---
netsh advfirewall firewall show rule name=BTNumarator-%PORT% >nul 2>&1
if not errorlevel 1 goto guvenlik_tamam
echo.
choice /c EH /n /m "Guvenlik duvarinda %PORT% numarali porta izin verilsin mi? Yonetici onayi istenebilir [E/H]: "
if errorlevel 2 goto guvenlik_tamam
powershell -NoProfile -Command "Start-Process -FilePath netsh -ArgumentList 'advfirewall firewall add rule name=BTNumarator-%PORT% dir=in action=allow protocol=TCP localport=%PORT% profile=any' -Verb RunAs -Wait" >nul 2>&1
if errorlevel 1 echo UYARI: Guvenlik duvari kurali eklenemedi. README'deki komutu yonetici olarak calistir.
:guvenlik_tamam

rem --- Panel ayaga kalkti mi? ---
set /a DENEME=0
:bekle
%PYCMD% -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:%PORT%/api/durum', timeout=1)" >nul 2>&1
if not errorlevel 1 goto hazir
set /a DENEME+=1
if %DENEME% GEQ 12 goto hazir_degil
timeout /t 1 /nobreak >nul
goto bekle

:hazir_degil
echo UYARI: Panel 12 saniyede yanit vermedi. Etiket gorunmuyorsa README'deki sorun giderme bolumune bak.

:hazir
set "ADRES=http://localhost:%PORT%"
for /f "delims=" %%i in ('%PYCMD% "%HEDEF%" --adres --port %PORT%') do set "ADRES=%%i"
echo.
echo Kurulum tamam.
echo   Ayar paneli          : %ADRES%   (bu bilgisayarda: http://localhost:%PORT%)
echo   Ilk yonetici sifresi : 1234   (panelden degistir)
echo   Her acilista kendiliginden baslar. Kaldirmak icin: kur.bat /kaldir
goto bitis

:kaldir
echo.
echo === BT Sinifi Sanal Numarator - Kaldirma ===
call :durdur
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v BTNumarator /f >nul 2>&1
timeout /t 1 /nobreak >nul
if exist "%HEDEF_DIZIN%" rmdir /s /q "%HEDEF_DIZIN%"
echo Kaldirildi.
echo Ayarlar ve ders programi silinmedi: %APPDATA%\bt-numarator
echo Guvenlik duvari kurali eklendiyse yonetici olarak kaldirabilirsin:
echo   netsh advfirewall firewall delete rule name=BTNumarator-8765
goto bitis

:port_hata
echo HATA: Port 1024 ile 65535 arasinda bir sayi olmali. Ornek: kur.bat 9000
goto bitis_hata

:bitis
echo.
pause
exit /b 0

:bitis_hata
echo.
pause
exit /b 1

:durdur
rem Calisan kopyayi kapat (yalnizca kurulu kopya; PowerShell kendi surecini disarida birakir)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*\BTNumarator\numarator.py*' -and $_.ProcessId -ne $PID } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
exit /b 0
