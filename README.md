# BT Sınıfı Sanal Numaratör

Bilgisayar laboratuvarındaki her öğrenci bilgisayarının ekranının **sağ altında** bilgisayar numarasını, o bilgisayarda oturan öğrencinin adını ve sınıfını gösteren küçük bir etiket. Ayarlar tarayıcıdan `IP:port` ile yapılır. Ders programı girilirse ad ve sınıf, belirlenen gün ve saatte kendiliğinden değişir.

| İsim açıkken | 30 saniye sonra (tıklayınca tekrar açılır) |
| --- | --- |
| ![İsim açık etiket](docs/etiket-acik.png) | ![Yalnızca numara kalan etiket](docs/etiket-kapali.png) |

## Özellikler

- Çerçevesiz, her zaman üstte duran etiket: büyük sarı numara, yanında öğrenci adı ve sınıfı
- Açıldıktan 30 saniye sonra isim kapanır, yalnızca numara kalır. Etikete tıklayınca isim yeniden görünür
- Tarayıcıdan ayar: `http://<bilgisayarın-ip-adresi>:8765`, yönetici şifresiyle korunur
- Ders programı: gün, başlangıç ve bitiş saatine göre sınıf ve ad otomatik değişir; ders dışında varsayılan bilgi görünür
- Bilgisayar açılınca otomatik başlar (panelden açılıp kapatılabilir)
- Windows ve Pardus/Linux; tek dosya, yalnızca Python standart kütüphanesi

## Hızlı kurulum

Önce projeyi indir: **Code → Download ZIP** (ZIP'i klasöre çıkar) ya da

```bash
git clone https://github.com/KULLANICI_ADI/bt-numarator.git
```

Kurulumu **öğrencilerin kullandığı kullanıcı hesabıyla** yap. Ayarlar ve otomatik başlatma kullanıcı hesabına özeldir.

### Windows

`kur.bat` dosyasına çift tıkla. Yönetici olmak gerekmez.

### Pardus / Linux

```bash
bash kur.sh
```

`sudo` ile çalıştırma. Betik yalnızca eksik paket varsa sudo şifresi sorar.

### Kurulum betikleri ne yapar?

1. Python 3.8+ ve tkinter var mı bakar. Eksikse kurar (Linux'ta `apt`/`dnf`/`pacman`, Windows'ta `winget`; winget yoksa indirme sayfasını açar)
2. `numarator.py` dosyasını kullanıcıya özel bir klasöre kopyalar. Böylece indirdiğin klasörü silebilirsin
3. Bilgisayar açılınca otomatik başlatmayı açar
4. Numaratörü hemen başlatır
5. Güvenlik duvarında portu açmayı önerir (Windows'ta sorar, Linux'ta `ufw` açıksa kendisi ekler)
6. Panel adresini ve ilk şifreyi ekrana yazar

Farklı port için: `kur.bat 9000` veya `bash kur.sh --port 9000`.

## Kullanım

### İlk ayar

Tarayıcıda `http://<bilgisayarın-ip-adresi>:8765` adresini aç. Ayarlanmamış bilgisayarın etiketi "Ayarlanmadı" yazar ve altında bu adresi gösterir, IP aramana gerek kalmaz.

1. Üstteki alana yönetici şifresini yaz. **İlk şifre `1234`**, "Şifreyi değiştir" bölümünden hemen değiştir
2. **Bilgisayar no** (en fazla 3 karakter), varsayılan **sınıf** (en fazla 12) ve **öğrenci adı** (en fazla 40) alanlarını doldurup Kaydet'e bas
3. Etiket anında güncellenir

Panelin üstündeki önizleme, o an ekranda ne görünüyorsa onu gösterir.

### Ders programı

Panelin "Ders programı" bölümünden:

1. Bir veya birkaç gün seç (Pzt–Paz)
2. Başlangıç saatini seç. Bitiş saati otomatik 40 dakika sonrasına ayarlanır, istersen değiştir
3. Sınıf ve öğrenci adını yaz (ikisinden biri yeterli), **Programa ekle**'ye bas

Seçtiğin gün ve saatte etiketteki sınıf ve ad kendiliğinden değişir. Ders bitince varsayılan bilgi geri gelir. Bilgisayar numarası hiç değişmez.

- Aynı gün içinde çakışan saatler eklenemez. Ardışık dersler (09:00–09:40, 09:40–10:20) sorunsuz çalışır
- Geçişler **bilgisayarın saatine** göre yapılır. Saat ve saat diliminin doğru olduğundan emin ol
- En fazla 300 kayıt tutulur

### Etiketin davranışı

- Program açıldıktan **30 saniye** sonra isim ve sınıf kapanır, yalnızca numara kalır
- Etikete tıklayınca isim 30 saniyeliğine açılır. İsim açıkken tekrar tıklarsan hemen kapanır
- Görünen bilgi değişince (yeni ders başlayınca ya da panelden numara, sınıf veya ad değiştirilince) isim 30 saniye görünür
- Ayarlanmamış bilgisayarda isim hiç kapanmaz (panel adresi görünsün diye)
- Süreyi değiştirmek için `numarator.py` içindeki `ISIM_SURESI` değerini düzenle

### Otomatik başlatma

Panelin altındaki "Otomatik başlatma" kutusundan açılıp kapatılır (yönetici şifresi gerekir). Komut satırından da yapılabilir:

```bash
python numarator.py --kur        # aç
python numarator.py --kaldir     # kapat
```

## Birden fazla bilgisayar

Kurulum betiğini her bilgisayarda çalıştır (USB bellekle ya da ağ paylaşımıyla). Numaraları tek tek panelden girebilir ya da API ile toplu verebilirsin. Aşağıdaki örnek, IP aralığındaki bilgisayarlara sırayla 1, 2, 3… numarası verir (sınıf ve ad boş kalır):

```bash
no=1
for ip in 192.168.1.{21..50}; do
  curl -s -X POST "http://$ip:8765/api/ayar" \
    -H "Content-Type: application/json" \
    -d "{\"sifre\":\"1234\",\"no\":\"$no\",\"sinif\":\"\",\"ad\":\"\"}" > /dev/null
  no=$((no+1))
done
```

## Elle çalıştırma

Kurulum betiği kullanmadan doğrudan da çalıştırabilirsin (Python 3.8+ ve tkinter gerekir):

```bash
python numarator.py                 # çalıştır (varsayılan port 8765)
python numarator.py --port 9000     # farklı port
python numarator.py --adres         # panel adresini yazdır ve çık
python numarator.py --kur           # bilgisayar açılınca otomatik başlat
python numarator.py --kaldir        # otomatik başlatmayı kaldır
```

Pardus/Debian'da tkinter yoksa: `sudo apt install python3-tk`

## Dosya konumları

| Ne | Windows | Linux |
| --- | --- | --- |
| Kurulu program | `%LOCALAPPDATA%\BTNumarator\numarator.py` | `~/.local/share/bt-numarator/numarator.py` |
| Ayarlar ve ders programı | `%APPDATA%\bt-numarator\ayar.json` | `~/.config/bt-numarator/ayar.json` |
| Otomatik başlatma | Kayıt defteri: `HKCU\...\Run` → `BTNumarator` | `~/.config/autostart/bt-numarator.desktop` |

## Güvenlik

- Panel, yönetici şifresiyle korunur ve yanlış şifre denemeleri 1 saniye geciktirilir
- Bağlantı **şifrelenmez (HTTP)** ve şifre ayar dosyasında düz metin olarak durur. Yalnızca güvenilir okul ağında kullan, varsayılan şifreyi mutlaka değiştir
- Panele ağdaki herkes erişebilir, şifreyi bilmeyen değişiklik yapamaz. Port internete açılmamalı

## Sorun giderme

**Panel açılmıyor.** İki bilgisayar aynı ağda mı? Güvenlik duvarında port açık mı?
- Windows (yönetici komut satırı): `netsh advfirewall firewall add rule name=BTNumarator-8765 dir=in action=allow protocol=TCP localport=8765 profile=any`
- Linux: `sudo ufw allow 8765/tcp`

**"Port 8765 kullanımda" uyarısı.** Numaratör zaten çalışıyordur ya da başka bir program o portu kullanıyordur. Başka bir port seç (`--port`).

**Etiket görünmüyor.** Programın çalıştığından emin ol (`http://localhost:8765` açılıyor mu?). Linux'ta `python3 -c "import tkinter"` hata veriyorsa `python3-tk` paketini kur. Wayland oturumunda etiket diğer pencerelerin arkasında kalırsa oturum açarken Xorg oturumunu seçmeyi dene.

**Etiket görev çubuğuna çok yakın ya da çok uzak (Linux).** `numarator.py` başındaki `ALT_BOSLUK_YEDEK` değerini ayarla.

**Ders programı yanlış saatte değişiyor.** Bilgisayarın saati ve saat dilimi yanlıştır, düzelt.

**Başka bir hesapla girince ayarlar yok.** Ayarlar ve otomatik başlatma kullanıcıya özeldir. O hesapta da kurulum yap.

## Kaldırma

```bash
kur.bat /kaldir          # Windows
bash kur.sh --kaldir     # Linux
```

Programı ve otomatik başlatmayı kaldırır. Ayarlar ve ders programı silinmez, istersen "Dosya konumları" tablosundaki klasörü de sil. Windows'ta güvenlik duvarı kuralı eklendiyse yönetici olarak kaldır: `netsh advfirewall firewall delete rule name=BTNumarator-8765`

## API

Panelin kullandığı uç noktalar, başka programlardan da çağrılabilir. Tüm `POST` isteklerinde gövdede `sifre` alanı zorunludur.

| Yöntem | Adres | Gövde |
| --- | --- | --- |
| GET | `/api/durum` | Şu anki bilgi, ders programı ve otomatik başlatma durumu |
| POST | `/api/ayar` | `no`, `sinif`, `ad`, isteğe bağlı `yeni_sifre` (üç alanı da değiştirir) |
| POST | `/api/program/ekle` | `gunler` (0 = Pazartesi … 6 = Pazar), `bas`, `bit` (`SS:DD`), `sinif`, `ad` |
| POST | `/api/program/sil` | `id` ya da `hepsi: true` |
| POST | `/api/otomatik` | `acik: true` / `false` |

```bash
curl -X POST http://192.168.1.23:8765/api/ayar \
  -H "Content-Type: application/json" \
  -d '{"sifre":"1234","no":"7","sinif":"9-A","ad":"Ayşe Demir"}'
```

## Klasör yapısı

```
bt-numarator/
├── numarator.py      # program (etiket + web paneli)
├── kur.sh            # Linux / Pardus kurulum betiği
├── kur.bat           # Windows kurulum betiği
├── README.md
└── docs/             # README görselleri
```
