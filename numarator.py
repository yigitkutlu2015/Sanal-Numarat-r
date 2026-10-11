#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BT Sınıfı Sanal Numaratör
=========================
Bilgisayar açılınca ekranın sağ altında bilgisayar numarasını, o bilgisayarda
oturan öğrencinin adını ve sınıfını gösterir. Ayarlar, aynı ağdaki herhangi bir
tarayıcıdan  http://<bilgisayarın-ip-adresi>:<port>  adresine girilerek yapılır.
Ders programına gün ve saat eklenirse, o gün ve saatte sınıf ile öğrenci adı
kendiliğinden değişir; ders dışında varsayılan bilgi görünür.
Açıldıktan ISIM_SURESI saniye sonra isim kısmı kapanır, yalnızca numara kalır;
etikete tıklanınca isim yeniden görünür. Otomatik başlatma panelden de açılıp kapatılır.

Kullanım:
    python numarator.py                 # çalıştır (varsayılan port 8765)
    python numarator.py --port 9000     # farklı port
    python numarator.py --kur           # bilgisayar açılınca otomatik başlat
    python numarator.py --kaldir        # otomatik başlatmayı kaldır
    python numarator.py --adres         # ayar paneli adresini yazdır ve çık

Gereksinim: Python 3.8+ (yalnızca standart kütüphane).
Pardus/Debian'da tkinter yoksa:  sudo apt install python3-tk
"""
import argparse
import hmac
import json
import os
import platform
import re
import secrets
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SISTEM = platform.system()  # "Windows" / "Linux"
VARSAYILAN_PORT = 8765
VARSAYILAN_SIFRE = "1234"   # ilk kurulumda geçerli; panelden değiştirilebilir

# Etiketin renkleri (web paneli de aynı paleti kullanır)
TAHTA = "#1E3B33"
CIZGI = "#34574C"
TEBESIR = "#F1EEE3"
SOLUK = "#A9BDB2"
SARI = "#F7C531"
MUREKKEP = "#1A1A14"

KENAR_BOSLUK = 14        # etiketin ekran kenarına uzaklığı (px)
ALT_BOSLUK_YEDEK = 48    # çalışma alanı bulunamazsa alt panel payı (px)
ISIM_SURESI = 30         # isim kısmının açık kalma süresi (saniye)


# --------------------------------------------------------------------------- #
#  Ayarlar
# --------------------------------------------------------------------------- #
def ayar_dosyasi():
    if SISTEM == "Windows":
        taban = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        taban = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return taban / "bt-numarator" / "ayar.json"


def temiz(deger, sinir):
    return " ".join(str(deger or "").split())[:sinir]


GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
SAAT_DESENI = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EN_COK_KAYIT = 300


class Hata(Exception):
    def __init__(self, kod, mesaj):
        super().__init__(mesaj)
        self.kod, self.mesaj = kod, mesaj


def ders_kaydi(k):
    """Dışarıdan gelen ders kaydını doğrular; geçersizse None döner."""
    if not isinstance(k, dict):
        return None
    try:
        gun = int(k["gun"])
    except (KeyError, TypeError, ValueError):
        return None
    bas, bit = str(k.get("bas", "")), str(k.get("bit", ""))
    sinif, ad = temiz(k.get("sinif"), 12), temiz(k.get("ad"), 40)
    if not (0 <= gun <= 6 and SAAT_DESENI.match(bas) and SAAT_DESENI.match(bit) and bas < bit and (sinif or ad)):
        return None
    return {"id": temiz(k.get("id"), 16) or secrets.token_hex(4),
            "gun": gun, "bas": bas, "bit": bit, "sinif": sinif, "ad": ad}


class Ayar:
    def __init__(self, dosya):
        self.dosya = Path(dosya)
        self.kilit = threading.Lock()
        self.veri = {"no": "", "sinif": "", "ad": "", "sifre": VARSAYILAN_SIFRE, "program": []}
        try:
            kayit = json.loads(self.dosya.read_text(encoding="utf-8"))
            for anahtar in ("no", "sinif", "ad", "sifre"):
                if isinstance(kayit.get(anahtar), str):
                    self.veri[anahtar] = kayit[anahtar]
            if isinstance(kayit.get("program"), list):
                program = (ders_kaydi(k) for k in kayit["program"])
                self.veri["program"] = [k for k in program if k][:EN_COK_KAYIT]
        except (OSError, ValueError, AttributeError):
            pass

    def _diske_yaz(self):
        try:
            self.dosya.parent.mkdir(parents=True, exist_ok=True)
            gecici = self.dosya.with_suffix(".tmp")
            gecici.write_text(json.dumps(self.veri, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(gecici, self.dosya)
        except OSError as hata:
            print("Ayar dosyası yazılamadı:", hata, file=sys.stderr)

    def _yetki(self, istek):
        """Kilit alınmışken çağrılır; şifre yanlışsa Hata fırlatır."""
        giris = str(istek.get("sifre", "")).encode("utf-8")
        if not hmac.compare_digest(giris, self.veri["sifre"].encode("utf-8")):
            raise Hata(403, "Şifre yanlış. Yönetici şifresini kontrol edip tekrar dene.")

    # -- okuma ----------------------------------------------------------- #
    def gecerli(self, simdi=None):
        """Şu an ekranda görünmesi gereken no / sınıf / ad.
        Ders programında şu ana denk gelen kayıt varsa onu, yoksa varsayılanı verir."""
        simdi = simdi or datetime.now()
        gun, saat = simdi.weekday(), simdi.strftime("%H:%M")
        with self.kilit:
            v = self.veri
            for k in v["program"]:
                if k["gun"] == gun and k["bas"] <= saat < k["bit"]:
                    return {"no": v["no"], "sinif": k["sinif"], "ad": k["ad"], "kaynak": "program",
                            "id": k["id"], "aralik": f"{GUNLER[gun]} {k['bas']}–{k['bit']}"}
            return {"no": v["no"], "sinif": v["sinif"], "ad": v["ad"], "kaynak": "varsayilan"}

    def durum(self):
        with self.kilit:
            v = self.veri
            ozet = {"no": v["no"], "sinif": v["sinif"], "ad": v["ad"],
                    "program": sorted((dict(k) for k in v["program"]), key=lambda k: (k["gun"], k["bas"]))}
        ozet["simdi"] = self.gecerli()
        ozet["otomatik"] = otomatik_acik()
        return ozet

    # -- yazma (hepsi yönetici şifresi ister) ---------------------------- #
    def guncelle(self, istek):
        with self.kilit:
            self._yetki(istek)
            yeni = str(istek.get("yeni_sifre", "")).strip()
            if yeni and len(yeni) < 4:
                raise Hata(400, "Yeni şifre en az 4 karakter olmalı.")
            self.veri["no"] = temiz(istek.get("no"), 3)
            self.veri["sinif"] = temiz(istek.get("sinif"), 12)
            self.veri["ad"] = temiz(istek.get("ad"), 40)
            if yeni:
                self.veri["sifre"] = yeni
            self._diske_yaz()

    def otomatik(self, istek, port):
        """Bilgisayar açılınca otomatik başlatmayı açar / kapatır."""
        with self.kilit:
            self._yetki(istek)
        try:
            otomatik_baslat(istek.get("acik") is True, port)
        except OSError as hata:
            raise Hata(500, f"Otomatik başlatma ayarlanamadı: {hata}")

    def program_ekle(self, istek):
        with self.kilit:
            self._yetki(istek)
            gunler = istek.get("gunler")
            gunler = sorted({g for g in gunler if isinstance(g, int) and 0 <= g <= 6}) if isinstance(gunler, list) else []
            if not gunler:
                raise Hata(400, "En az bir gün seç.")
            bas, bit = str(istek.get("bas", "")), str(istek.get("bit", ""))
            if not (SAAT_DESENI.match(bas) and SAAT_DESENI.match(bit)):
                raise Hata(400, "Başlangıç ve bitiş saatini seç (örn. 09:00).")
            if bas >= bit:
                raise Hata(400, "Bitiş saati başlangıç saatinden sonra olmalı.")
            sinif, ad = temiz(istek.get("sinif"), 12), temiz(istek.get("ad"), 40)
            if not (sinif or ad):
                raise Hata(400, "Sınıf veya öğrenci adı yaz.")
            for g in gunler:
                for k in self.veri["program"]:
                    if k["gun"] == g and bas < k["bit"] and k["bas"] < bit:
                        raise Hata(400, f"{GUNLER[g]} günü {k['bas']}–{k['bit']} kaydıyla çakışıyor.")
            if len(self.veri["program"]) + len(gunler) > EN_COK_KAYIT:
                raise Hata(400, "Çok fazla kayıt var; eskilerini sil.")
            for g in gunler:
                self.veri["program"].append({"id": secrets.token_hex(4), "gun": g, "bas": bas, "bit": bit,
                                             "sinif": sinif, "ad": ad})
            self._diske_yaz()

    def program_sil(self, istek):
        with self.kilit:
            self._yetki(istek)
            if istek.get("hepsi") is True:
                self.veri["program"] = []
            else:
                kimlik = str(istek.get("id", ""))
                kalan = [k for k in self.veri["program"] if k["id"] != kimlik]
                if len(kalan) == len(self.veri["program"]):
                    raise Hata(404, "Kayıt bulunamadı.")
                self.veri["program"] = kalan
            self._diske_yaz()


def yerel_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # paket göndermez, sadece yolu seçer
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def adres_metni(port):
    return f"http://{yerel_ip()}:{port}"


# --------------------------------------------------------------------------- #
#  Web paneli (IP:port)
# --------------------------------------------------------------------------- #
SAYFA = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Numaratör ayarı</title>
<style>
:root{color-scheme:dark;--tahta:#1E3B33;--zemin:#142822;--tebesir:#F1EEE3;--soluk:#A9BDB2;--sari:#F7C531;--murekkep:#1A1A14;--hata:#FF9B88;--cizgi:#34574C}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--zemin);color:var(--tebesir);font:16px/1.5 "Segoe UI","Noto Sans","DejaVu Sans",system-ui,sans-serif;min-height:100vh;padding:32px 16px 48px}
main{max-width:460px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 4px;font-weight:700}
h2{font-size:1.15rem;margin:0 0 4px;font-weight:700}
.alt{color:var(--soluk);margin:0 0 20px}
.not{color:var(--soluk);margin:0 0 16px;font-size:.92rem}
.etiket{display:inline-flex;align-items:stretch;background:var(--tahta);border:1px solid var(--cizgi);border-radius:10px;overflow:hidden;margin-bottom:24px;max-width:100%}
.no{background:var(--sari);color:var(--murekkep);font-weight:800;font-size:2.2rem;line-height:1;min-width:68px;padding:14px 16px;display:flex;align-items:center;justify-content:center}
.kim{padding:10px 20px 10px 14px;display:flex;flex-direction:column;justify-content:center;min-width:0}
.ad{font-weight:700;font-size:1.1rem;overflow-wrap:anywhere}
.sinif{color:var(--soluk);font-size:.9rem}
section{border-top:1px solid var(--cizgi);padding-top:22px;margin-top:26px}
.satir{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:block;margin-bottom:14px;font-size:.92rem;color:var(--soluk)}
input{display:block;width:100%;margin-top:4px;padding:10px 12px;font:inherit;color:var(--tebesir);background:var(--tahta);border:1px solid var(--cizgi);border-radius:8px}
input:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--sari);outline-offset:2px}
fieldset{border:0;padding:0;margin:0 0 14px}
legend{padding:0;margin-bottom:6px;font-size:.92rem;color:var(--soluk)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chips label{margin:0;position:relative}
.chips input{position:absolute;opacity:0;width:1px;height:1px;margin:0}
.chips span{display:block;padding:7px 12px;border:1px solid var(--cizgi);border-radius:8px;background:var(--tahta);color:var(--tebesir);font-size:.9rem;cursor:pointer;user-select:none}
.chips input:checked + span{background:var(--sari);color:var(--murekkep);border-color:var(--sari);font-weight:700}
.chips input:focus-visible + span{outline:2px solid var(--sari);outline-offset:2px}
details{margin-bottom:16px;color:var(--soluk);font-size:.92rem}
summary{cursor:pointer;margin-bottom:10px}
.eylem{display:flex;gap:10px}
button{font:inherit;font-weight:700;padding:10px 22px;border-radius:8px;border:1px solid var(--cizgi);cursor:pointer}
.ana{background:var(--sari);color:var(--murekkep);border-color:var(--sari)}
.ikincil{background:transparent;color:var(--tebesir)}
.liste{list-style:none;margin:0 0 12px;padding:0}
.liste li{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 12px;border:1px solid var(--cizgi);border-left-width:4px;border-radius:8px;margin-bottom:8px;background:var(--tahta)}
.liste li.aktif{border-left-color:var(--sari)}
.liste li.bos{display:block;border-style:dashed;background:transparent;color:var(--soluk)}
.zaman{font-weight:700}
.kim2{color:var(--soluk);font-size:.92rem;overflow-wrap:anywhere}
.kucuk{padding:6px 12px;font-size:.9rem;font-weight:600;background:transparent;color:var(--tebesir)}
.durum{min-height:1.5em;margin:12px 0 0;color:var(--soluk)}
.durum.hata{color:var(--hata)}
.anahtar{display:flex;align-items:center;gap:10px;margin:0;font-size:1rem;color:var(--tebesir);cursor:pointer}
.anahtar input{display:inline-block;width:20px;height:20px;margin:0;accent-color:var(--sari)}
@media (max-width:420px){.satir{grid-template-columns:1fr}}
</style>
</head>
<body>
<main>
  <h1>Bu bilgisayarın etiketi</h1>
  <p class="alt" id="kaynak">Ekranın sağ altında bu şekilde görünüyor.</p>

  <div class="etiket" aria-hidden="true">
    <div class="no" id="o-no">?</div>
    <div class="kim"><div class="ad" id="o-ad">Ayarlanmadı</div><div class="sinif" id="o-sinif"></div></div>
  </div>

  <label>Yönetici şifresi<input id="sifre" type="password" autocomplete="off"></label>

  <section>
    <h2>Bilgisayar ve varsayılan bilgi</h2>
    <p class="not">Ders programında olmayan saatlerde ekranda bu sınıf ve ad görünür.</p>
    <form id="f1" autocomplete="off">
      <div class="satir">
        <label>Bilgisayar no<input id="no" maxlength="3"></label>
        <label>Sınıf<input id="sinif" maxlength="12" placeholder="9-A"></label>
      </div>
      <label>Öğrenci adı<input id="ad" maxlength="40"></label>
      <details>
        <summary>Şifreyi değiştir</summary>
        <label>Yeni şifre (en az 4 karakter)<input id="yeni" type="password" autocomplete="off"></label>
      </details>
      <div class="eylem">
        <button class="ana" type="submit">Kaydet</button>
        <button class="ikincil" type="button" id="temizle">Temizle</button>
      </div>
      <p class="durum" id="durum-1" role="status"></p>
    </form>
  </section>

  <section>
    <h2>Ders programı</h2>
    <p class="not">Seçtiğin gün ve saatte etiketteki sınıf ve ad kendiliğinden değişir. Ders bitince varsayılan bilgi geri gelir.</p>
    <ul class="liste" id="liste"></ul>
    <button class="kucuk" type="button" id="hepsi" hidden>Tümünü sil</button>

    <form id="f2" autocomplete="off" style="margin-top:18px">
      <fieldset>
        <legend>Günler</legend>
        <div class="chips">
          <label><input type="checkbox" value="0"><span>Pzt</span></label>
          <label><input type="checkbox" value="1"><span>Sal</span></label>
          <label><input type="checkbox" value="2"><span>Çar</span></label>
          <label><input type="checkbox" value="3"><span>Per</span></label>
          <label><input type="checkbox" value="4"><span>Cum</span></label>
          <label><input type="checkbox" value="5"><span>Cmt</span></label>
          <label><input type="checkbox" value="6"><span>Paz</span></label>
        </div>
      </fieldset>
      <div class="satir">
        <label>Başlangıç<input id="bas" type="time"></label>
        <label>Bitiş<input id="bit" type="time"></label>
      </div>
      <div class="satir">
        <label>Sınıf<input id="psinif" maxlength="12" placeholder="9-A"></label>
        <label>Öğrenci adı<input id="pad" maxlength="40"></label>
      </div>
      <button class="ana" type="submit">Programa ekle</button>
      <p class="durum" id="durum-2" role="status"></p>
    </form>
  </section>

  <section>
    <h2>Otomatik başlatma</h2>
    <p class="not">Açıkken bilgisayar her açıldığında numaratör kendiliğinden başlar. Değiştirmek için yukarıdaki yönetici şifresi gerekir.</p>
    <label class="anahtar"><input type="checkbox" id="oto">Bilgisayar açılınca numaratör açılsın</label>
    <p class="durum" id="durum-3" role="status"></p>
  </section>
</main>
<script>
const $=id=>document.getElementById(id);
const GUNLER=["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"];

function bildir(id,mesaj,hata){const d=$(id);d.textContent=mesaj;d.className="durum"+(hata?" hata":"");}

function liste(program,aktif){
  const ul=$("liste");ul.textContent="";
  $("hepsi").hidden=!program.length;
  if(!program.length){
    const li=document.createElement("li");li.className="bos";
    li.textContent="Henüz kayıt yok. Aşağıdan gün ve saat ekle.";
    ul.appendChild(li);return;
  }
  program.forEach(k=>{
    const li=document.createElement("li");
    if(k.id===aktif)li.className="aktif";
    const sol=document.createElement("div");
    const z=document.createElement("div");z.className="zaman";z.textContent=GUNLER[k.gun]+" "+k.bas+"–"+k.bit;
    const w=document.createElement("div");w.className="kim2";w.textContent=[k.ad,k.sinif].filter(Boolean).join(", ");
    sol.append(z,w);
    const b=document.createElement("button");
    b.type="button";b.className="kucuk";b.textContent="Sil";
    b.setAttribute("aria-label",GUNLER[k.gun]+" "+k.bas+" kaydını sil");
    b.addEventListener("click",()=>istek("/api/program/sil",{id:k.id},"durum-2","Kayıt silindi."));
    li.append(sol,b);ul.appendChild(li);
  });
}

function ciz(d){
  const s=d.simdi,hazir=s.no||s.ad||s.sinif;
  $("o-no").textContent=s.no||"?";
  $("o-ad").textContent=s.ad||s.sinif||(hazir?"Boş":"Ayarlanmadı");
  $("o-sinif").textContent=s.ad?s.sinif:"";
  $("kaynak").textContent=s.kaynak==="program"
    ?"Şu an ders programından görünüyor: "+s.aralik+"."
    :d.program.length?"Şu an ders saati dışında; varsayılan bilgi görünüyor."
    :"Ekranın sağ altında bu şekilde görünüyor.";
  liste(d.program,s.id);
  $("oto").checked=!!d.otomatik;
}

async function istek(yol,ek,durumId,basari){
  const govde=Object.assign({sifre:$("sifre").value},ek);
  bildir(durumId,"Kaydediliyor…");
  try{
    const r=await fetch(yol,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(govde)});
    const v=await r.json();
    if(!r.ok){bildir(durumId,v.hata||"Kaydedilemedi.",true);return false;}
    try{sessionStorage.setItem("sifre",govde.yeni_sifre||govde.sifre);}catch(e){}
    ciz(v);bildir(durumId,basari);return true;
  }catch(e){bildir(durumId,"Bu bilgisayara ulaşılamadı.",true);return false;}
}

async function yukle(){
  try{
    const d=await (await fetch("/api/durum",{cache:"no-store"})).json();
    $("no").value=d.no||"";$("sinif").value=d.sinif||"";$("ad").value=d.ad||"";
    ciz(d);
  }catch(e){bildir("durum-1","Bu bilgisayara ulaşılamadı. Programın çalıştığından emin ol.",true);}
  try{$("sifre").value=sessionStorage.getItem("sifre")||"";}catch(e){}
}

$("f1").addEventListener("submit",async e=>{
  e.preventDefault();
  const yeni=$("yeni").value;
  const tamam=await istek("/api/ayar",{no:$("no").value,sinif:$("sinif").value,ad:$("ad").value,yeni_sifre:yeni},
    "durum-1","Kaydedildi. Ekrandaki etiket güncellendi.");
  if(tamam&&yeni){$("sifre").value=yeni;$("yeni").value="";}
});

$("temizle").addEventListener("click",async()=>{
  if(!confirm("Bilgisayar no ve varsayılan bilgi silinsin mi?"))return;
  if(await istek("/api/ayar",{no:"",sinif:"",ad:""},"durum-1","Temizlendi.")){
    $("no").value="";$("sinif").value="";$("ad").value="";
  }
});

function kirk(saat){
  const p=saat.split(":");if(p.length!==2)return "";
  const t=Math.min(+p[0]*60+ +p[1]+40,23*60+59);
  return String(Math.floor(t/60)).padStart(2,"0")+":"+String(t%60).padStart(2,"0");
}
$("bas").addEventListener("change",()=>{
  const bit=$("bit");
  if($("bas").value&&(!bit.value||bit.dataset.oto==="1")){bit.value=kirk($("bas").value);bit.dataset.oto="1";}
});
$("bit").addEventListener("input",()=>{$("bit").dataset.oto="0";});

$("f2").addEventListener("submit",async e=>{
  e.preventDefault();
  const gunler=[...document.querySelectorAll("#f2 .chips input:checked")].map(i=>+i.value);
  const tamam=await istek("/api/program/ekle",
    {gunler,bas:$("bas").value,bit:$("bit").value,sinif:$("psinif").value,ad:$("pad").value},
    "durum-2","Programa eklendi.");
  if(tamam){$("psinif").value="";$("pad").value="";}
});

$("hepsi").addEventListener("click",()=>{
  if(confirm("Ders programındaki bütün kayıtlar silinsin mi?"))istek("/api/program/sil",{hepsi:true},"durum-2","Program temizlendi.");
});

$("oto").addEventListener("change",async()=>{
  const acik=$("oto").checked;
  const tamam=await istek("/api/otomatik",{acik},"durum-3",
    acik?"Açıldı. Bilgisayar açılınca numaratör kendiliğinden başlayacak.":"Otomatik başlatma kapatıldı.");
  if(!tamam)$("oto").checked=!acik;
});

setInterval(async()=>{
  try{ciz(await (await fetch("/api/durum",{cache:"no-store"})).json());}catch(e){}
},15000);
yukle();
</script>
</body>
</html>
"""


class Isleyici(BaseHTTPRequestHandler):
    ayar = None  # main() içinde atanır
    port = VARSAYILAN_PORT
    server_version = "BTNumarator"

    def log_message(self, *args):
        pass

    def _yanit(self, kod, icerik, tur="application/json; charset=utf-8"):
        if not isinstance(icerik, (bytes, str)):
            icerik = json.dumps(icerik, ensure_ascii=False)
        veri = icerik if isinstance(icerik, bytes) else icerik.encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(veri)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(veri)

    def do_GET(self):
        yol = self.path.split("?")[0]
        if yol == "/":
            self._yanit(200, SAYFA, "text/html; charset=utf-8")
        elif yol == "/api/durum":
            self._yanit(200, self.ayar.durum())
        else:
            self._yanit(404, {"hata": "Bulunamadı"})

    def do_POST(self):
        islemler = {"/api/ayar": self.ayar.guncelle,
                    "/api/otomatik": lambda istek: self.ayar.otomatik(istek, self.port),
                    "/api/program/ekle": self.ayar.program_ekle,
                    "/api/program/sil": self.ayar.program_sil}
        islem = islemler.get(self.path.split("?")[0])
        if islem is None:
            return self._yanit(404, {"hata": "Bulunamadı"})
        try:
            uzunluk = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            uzunluk = 0
        if uzunluk <= 0 or uzunluk > 8192:
            return self._yanit(400, {"hata": "Geçersiz istek."})
        try:
            istek = json.loads(self.rfile.read(uzunluk).decode("utf-8"))
            if not isinstance(istek, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return self._yanit(400, {"hata": "Geçersiz istek."})

        try:
            islem(istek)
        except Hata as h:
            if h.kod == 403:
                time.sleep(1)  # şifre denemelerini yavaşlat
            return self._yanit(h.kod, {"hata": h.mesaj})
        self._yanit(200, {"ok": True, **self.ayar.durum()})


# --------------------------------------------------------------------------- #
#  Ekranın sağ altındaki etiket
# --------------------------------------------------------------------------- #
def calisma_alani_sag_alt(kok):
    """Görev çubuğunun üstünde kalan çalışma alanının sağ-alt köşesi."""
    if SISTEM == "Windows":
        try:
            import ctypes
            from ctypes import wintypes
            dikdortgen = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(dikdortgen), 0):  # SPI_GETWORKAREA
                return dikdortgen.right, dikdortgen.bottom
        except Exception:
            pass
    return kok.winfo_screenwidth(), kok.winfo_screenheight() - ALT_BOSLUK_YEDEK


class Etiket:
    def __init__(self, ayar, port):
        import tkinter as tk
        from tkinter import font as tkfont

        if SISTEM == "Windows":
            try:  # net görüntü için, Tk penceresinden önce
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        self.ayar, self.port = ayar, port
        self.son_veri, self.hazir, self.adres = None, False, ""
        self.isim_bitis, self.isim_gorunur = 0.0, True

        self.kok = tk.Tk()
        self.kok.title("BT Numaratör")
        self.kok.overrideredirect(True)           # çerçevesiz
        self.kok.attributes("-topmost", True)     # hep üstte
        try:
            self.kok.attributes("-alpha", 0.94)
        except tk.TclError:
            pass
        self.kok.configure(bg=CIZGI, padx=1, pady=1)

        aileler = set(tkfont.families(self.kok))
        aile = next((f for f in ("Segoe UI", "Noto Sans", "DejaVu Sans", "Liberation Sans", "Arial") if f in aileler),
                    "Helvetica")

        govde = tk.Frame(self.kok, bg=TAHTA)
        govde.pack()
        self.no = tk.Label(govde, font=(aile, 30, "bold"), bg=SARI, fg=MUREKKEP, width=3, padx=10)
        self.no.pack(side="left", fill="y")
        self.sag = tk.Frame(govde, bg=TAHTA)
        self.sag.pack(side="left", padx=(14, 20), pady=8)
        self.ad = tk.Label(self.sag, font=(aile, 15, "bold"), bg=TAHTA, fg=TEBESIR, anchor="w", justify="left",
                           wraplength=340)
        self.ad.pack(anchor="w")
        self.alt = tk.Label(self.sag, font=(aile, 11), bg=TAHTA, fg=SOLUK, anchor="w", justify="left")
        self.alt.pack(anchor="w")

        # Tıklayınca ismi göster / gizle. Tk, alt parçalardaki tıklamayı pencere
        # bağlamasına da ilettiği için yalnızca pencereye bağlamak yeterli.
        self.kok.config(cursor="hand2")
        self.kok.bind("<Button-1>", self.tikla)

    def ciz(self, veri=None):
        veri = veri or self.ayar.gecerli()
        self.son_veri = veri
        self.hazir = bool(veri["no"] or veri["ad"] or veri["sinif"])
        self.isim_bitis = time.monotonic() + ISIM_SURESI  # yeni bilgi gelince isim bir süre görünsün
        self.no.config(text=veri["no"] or "?")
        if self.hazir:
            self.ad.config(text=veri["ad"] or veri["sinif"] or "Boş")
            self.alt.config(text=veri["sinif"] if veri["ad"] else "")
        else:  # ayarlanmamışsa öğretmen adresi görsün
            self.adres = adres_metni(self.port)
            self.ad.config(text="Ayarlanmadı")
            self.alt.config(text=self.adres)
        self.yerlestir()
        self.konumla()

    def yerlestir(self):
        """İsim kısmını süreye göre açar / kapatır. Ayarlanmamışken hep açık kalır (adres görünsün)."""
        gorunur = (not self.hazir) or time.monotonic() < self.isim_bitis
        if gorunur == self.isim_gorunur:
            return
        self.isim_gorunur = gorunur
        if gorunur:
            self.sag.pack(side="left", padx=(14, 20), pady=8)
        else:
            self.sag.pack_forget()
        self.konumla()

    def tikla(self, olay=None):
        if not self.hazir:
            return
        self.isim_bitis = 0.0 if self.isim_gorunur else time.monotonic() + ISIM_SURESI
        self.yerlestir()

    def konumla(self):
        self.kok.update_idletasks()
        w, h = self.kok.winfo_reqwidth(), self.kok.winfo_reqheight()
        sag, alt = calisma_alani_sag_alt(self.kok)
        self.kok.geometry(f"{w}x{h}+{sag - w - KENAR_BOSLUK}+{alt - h - KENAR_BOSLUK}")

    def dongu(self):
        veri = self.ayar.gecerli()  # ders saati gelince / bitince burada değişir
        if veri != self.son_veri:
            self.ciz(veri)
        elif not self.hazir and adres_metni(self.port) != self.adres:  # ağ sonradan geldiyse
            self.ciz(veri)
        else:
            self.yerlestir()  # süre dolduysa ismi kapat
        self.kok.lift()
        self.kok.attributes("-topmost", True)
        self.kok.after(1000, self.dongu)

    def calistir(self):
        self.ciz()
        self.kok.after(1000, self.dongu)
        self.kok.mainloop()


# --------------------------------------------------------------------------- #
#  Bilgisayar açılınca otomatik başlatma
# --------------------------------------------------------------------------- #
def _tirnakla(parca):
    return f'"{parca}"' if " " in parca else parca


def baslatma_komutu(port):
    if getattr(sys, "frozen", False):  # PyInstaller ile paketlenmişse
        return [sys.executable, "--port", str(port)]
    yurutucu = sys.executable
    if SISTEM == "Windows":
        pencere_siz = Path(yurutucu).with_name("pythonw.exe")  # konsol penceresi açmasın
        if pencere_siz.exists():
            yurutucu = str(pencere_siz)
    return [yurutucu, str(Path(__file__).resolve()), "--port", str(port)]


RUN_YOLU = r"Software\Microsoft\Windows\CurrentVersion\Run"


def linux_otomatik_dosyasi():
    return Path.home() / ".config" / "autostart" / "bt-numarator.desktop"


def otomatik_acik():
    """Bu kullanıcı için otomatik başlatma açık mı?"""
    if SISTEM == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_YOLU) as anahtar:
                winreg.QueryValueEx(anahtar, "BTNumarator")
            return True
        except OSError:
            return False
    return linux_otomatik_dosyasi().exists()


def otomatik_baslat(ac, port):
    komut = " ".join(_tirnakla(p) for p in baslatma_komutu(port))
    if SISTEM == "Windows":
        import winreg
        anahtar = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_YOLU, 0, winreg.KEY_SET_VALUE)
        try:
            if ac:
                winreg.SetValueEx(anahtar, "BTNumarator", 0, winreg.REG_SZ, komut)
            else:
                try:
                    winreg.DeleteValue(anahtar, "BTNumarator")
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(anahtar)
    else:
        dosya = linux_otomatik_dosyasi()
        if ac:
            dosya.parent.mkdir(parents=True, exist_ok=True)
            dosya.write_text(
                "[Desktop Entry]\nType=Application\nName=BT Numaratör\n"
                f"Exec={komut}\nTerminal=false\nX-GNOME-Autostart-Delay=5\n",
                encoding="utf-8")
        elif dosya.exists():
            dosya.unlink()


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="BT sınıfı sanal numaratör")
    ap.add_argument("--port", type=int, default=VARSAYILAN_PORT, help="ayar paneli portu (varsayılan 8765)")
    ap.add_argument("--ayar-dosyasi", help="ayar dosyasının yolu (isteğe bağlı)")
    ap.add_argument("--kur", action="store_true", help="bilgisayar açılınca otomatik başlat")
    ap.add_argument("--kaldir", action="store_true", help="otomatik başlatmayı kaldır")
    ap.add_argument("--adres", action="store_true", help="ayar paneli adresini yazdır ve çık")
    a = ap.parse_args()

    if a.adres:
        print(adres_metni(a.port))
        return 0

    if a.kur or a.kaldir:
        otomatik_baslat(a.kur, a.port)
        print("Otomatik başlatma", "açıldı." if a.kur else "kaldırıldı.")
        return 0

    Isleyici.ayar = Ayar(a.ayar_dosyasi or ayar_dosyasi())
    Isleyici.port = a.port
    try:
        sunucu = ThreadingHTTPServer(("0.0.0.0", a.port), Isleyici)
    except OSError:
        print(f"Port {a.port} kullanımda; numaratör zaten çalışıyor olabilir.", file=sys.stderr)
        return 1
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()

    try:
        etiket = Etiket(Isleyici.ayar, a.port)
    except ImportError:
        print("tkinter bulunamadı. Pardus/Debian için:  sudo apt install python3-tk", file=sys.stderr)
        return 1
    etiket.calistir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
