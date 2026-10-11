#!/usr/bin/env bash
# BT Sınıfı Sanal Numaratör - Linux / Pardus kurulum betiği
#
# Kullanım:
#   bash kur.sh                  # kur, otomatik başlatmayı aç ve şimdi başlat (port 8765)
#   bash kur.sh --port 9000      # farklı port ile kur
#   bash kur.sh --kaldir         # kaldır
#
# Betik sudo ile DEĞİL, öğrencilerin kullandığı kullanıcı hesabıyla çalıştırılır.
# Yalnızca eksik paketler (python3, python3-tk) için sudo şifresi sorabilir.
set -euo pipefail

PORT=8765
KALDIR=0
KAYNAK_DIZIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEDEF_DIZIN="${XDG_DATA_HOME:-$HOME/.local/share}/bt-numarator"
HEDEF="$HEDEF_DIZIN/numarator.py"

bilgi()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
uyari()  { printf '\033[1;33m!! \033[0m %s\n' "$*"; }
hata()   { printf '\033[1;31mHATA:\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --port)
      [ $# -ge 2 ] || hata "--port için bir sayı yaz (örn. --port 9000)."
      PORT="$2"; shift 2 ;;
    --kaldir) KALDIR=1; shift ;;
    -h|--yardim) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) hata "Bilinmeyen seçenek: $1 (yardım için: bash kur.sh --yardim)" ;;
  esac
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
  hata "Port 1024 ile 65535 arasında bir sayı olmalı."
fi

[ "$(id -u)" -ne 0 ] \
  || hata "Betiği sudo/root ile çalıştırma. Öğrencilerin kullandığı kullanıcı hesabıyla çalıştır (otomatik başlatma kullanıcıya özeldir)."

durdur() {  # çalışan kopyayı kapat (yalnızca bu kullanıcının, yalnızca kurulu kopya)
  if command -v pkill >/dev/null 2>&1; then
    pkill -u "$(id -u)" -f "$HEDEF" 2>/dev/null || true
  fi
}

# ---------------------------------------------------------------- kaldır --
if [ "$KALDIR" -eq 1 ]; then
  bilgi "Numaratör kaldırılıyor..."
  durdur
  rm -f "$HOME/.config/autostart/bt-numarator.desktop"
  case "$HEDEF_DIZIN" in
    */bt-numarator) rm -rf "$HEDEF_DIZIN" ;;
    *) hata "Beklenmeyen kurulum dizini, silinmedi: $HEDEF_DIZIN" ;;
  esac
  bilgi "Kaldırıldı."
  echo "    Ayarların ve ders programın silinmedi: ${XDG_CONFIG_HOME:-$HOME/.config}/bt-numarator"
  echo "    Tamamen silmek istersen bu klasörü de sil."
  exit 0
fi

# ----------------------------------------------------------------- kurul --
[ -f "$KAYNAK_DIZIN/numarator.py" ] \
  || hata "numarator.py bu betikle aynı klasörde olmalı ($KAYNAK_DIZIN)."

paket_kur() {  # $1 = apt adı, $2 = dnf adı, $3 = pacman adı
  command -v sudo >/dev/null 2>&1 \
    || hata "Eksik paket var ama sudo bulunamadı. Yönetici olarak şunu kur: $1"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y "$1" || { sudo apt-get update && sudo apt-get install -y "$1"; }
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y "$2"
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --noconfirm "$3"
  else
    hata "Paket yöneticisi tanınmadı. Elle kur: $1"
  fi
}

bilgi "Python kontrol ediliyor..."
command -v python3 >/dev/null 2>&1 || { bilgi "Python 3 kuruluyor..."; paket_kur python3 python3 python; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
  || hata "Python 3.8 veya üstü gerekli."
if ! python3 -c 'import tkinter' 2>/dev/null; then
  bilgi "tkinter kuruluyor (python3-tk)..."
  paket_kur python3-tk python3-tkinter tk
  python3 -c 'import tkinter' 2>/dev/null || hata "tkinter kurulamadı."
fi

bilgi "Dosyalar kopyalanıyor: $HEDEF_DIZIN"
durdur  # eski sürüm çalışıyorsa kapat; ayarlar korunur
mkdir -p "$HEDEF_DIZIN"
[ "$KAYNAK_DIZIN/numarator.py" -ef "$HEDEF" ] || install -m 0644 "$KAYNAK_DIZIN/numarator.py" "$HEDEF"

if command -v ufw >/dev/null 2>&1 && systemctl is-active --quiet ufw 2>/dev/null; then
  bilgi "Güvenlik duvarında $PORT/tcp portuna izin veriliyor (ufw)..."
  sudo ufw allow "$PORT/tcp" >/dev/null || uyari "ufw kuralı eklenemedi; paneli açamazsan elle ekle: sudo ufw allow $PORT/tcp"
fi

bilgi "Bilgisayar açılınca otomatik başlatma ayarlanıyor..."
python3 "$HEDEF" --kur --port "$PORT"

if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  bilgi "Numaratör başlatılıyor..."
  setsid nohup python3 "$HEDEF" --port "$PORT" >/dev/null 2>&1 &
  HAZIR=0
  for _ in $(seq 1 20); do
    if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/api/durum', timeout=1)" 2>/dev/null; then
      HAZIR=1; break
    fi
    sleep 0.5
  done
  [ "$HAZIR" -eq 1 ] || uyari "Panel 10 saniyede yanıt vermedi. Etiket görünmüyorsa README'deki sorun giderme bölümüne bak."
else
  uyari "Grafik oturum bulunamadı; numaratör bir sonraki oturum açılışında kendiliğinden başlayacak."
fi

ADRES="$(python3 "$HEDEF" --adres --port "$PORT")"
echo
bilgi "Kurulum tamam."
echo "    Ayar paneli          : $ADRES   (bu bilgisayarda: http://localhost:$PORT)"
echo "    İlk yönetici şifresi : 1234   (panelden değiştir)"
echo "    Her açılışta kendiliğinden başlar. Kaldırmak için: bash kur.sh --kaldir"
