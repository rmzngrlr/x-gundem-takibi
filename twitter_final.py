import streamlit as st
import time
import os
import subprocess
import string
import base64
import re
import random
try:
    import winsound
except ImportError:
    winsound = None
import undetected_chromedriver as uc
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime, timedelta
from groq import Groq
import json
import hashlib
import firebase_admin
from firebase_admin import credentials, messaging, db
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher

# ==========================================
# ⚙️ SABİT AYARLAR
# ==========================================
FIREBASE_DB_URL = "https://x-gundem-raporu-default-rtdb.europe-west1.firebasedatabase.app"
PWA_URL = "https://x-gundem-raporu.web.app"
FIREBASE_WEB_API_KEY = "AIzaSyAgIWcLB_yOas3gQ8g5GrJJcala5SGovEU"
BUFFER_SURESI = 600  # 10 Dakika

def get_groq_api_key():
    key = os.getenv("GROQ_API_KEY")
    if key: return key
    try:
        key = st.secrets.get("GROQ_API_KEY")
        if key: return key
    except Exception:
        pass
    return "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"

GROQ_API_KEY = get_groq_api_key()

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
    except Exception as e:
        st.error(f"Firebase Bağlantı Hatası: {e}")

st.set_page_config(page_title="X Gündem Takibi", page_icon="ikon.png", layout="wide")

# --- CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    /* Hide Streamlit header anchors */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🔐 AUTHENTICATION & LOGIN
# ==========================================
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'driver' not in st.session_state: st.session_state.driver = None
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'arsiv' not in st.session_state: st.session_state.arsiv = [] 
if 'gordugum_linkler' not in st.session_state: st.session_state.gordugum_linkler = set()
if 'raporlanan_ozetler' not in st.session_state: st.session_state.raporlanan_ozetler = []
if 'raporlanan_linkler' not in st.session_state: st.session_state.raporlanan_linkler = set() # Yeni: Link bazlı kontrol
if 'tweet_buffer' not in st.session_state: st.session_state.tweet_buffer = [] # Yeni: Tweet Havuzu
if 'db_history_loaded' not in st.session_state: st.session_state.db_history_loaded = False
if 'session_checked' not in st.session_state: st.session_state.session_checked = False

def get_img_as_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f: return base64.b64encode(f.read()).decode()
    return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_kurumsal(kurum_adi, sifre):
    try:
        ref = db.reference(f'tenants_auth/{kurum_adi}')
        data = ref.get()
        if not data:
            return None, "Kurum bulunamadı."
        
        # Şifre Kontrolü
        if data.get('password_hash') != hash_password(sifre):
            return None, "Hatalı şifre."
        
        # Aktiflik Kontrolü
        if not data.get('active', True):
            return None, "Erişiminiz yönetici tarafından durdurulmuştur."
            
        return kurum_adi, None
    except Exception as e:
        return None, str(e)

# --- BİLDİRİM ABONELİĞİ YÖNETİMİ (BACKEND PROCESS) ---
def bekleyen_aboneleri_isle(tid):
    """
    Abone bekleyenler listesini tarar.
    Bu tenant'a ait olanları bulur.
    İlgili topic'lere (std ve ios) abone yapar.
    Listeden siler.
    """
    try:
        ref_bekleyen = db.reference('abone_bekleyenler')
        snapshot = ref_bekleyen.get()
        
        if snapshot:
            tokens_to_sub = []
            keys_to_del = []
            
            tokens_std = []
            tokens_ios = []
            keys_to_del = []
            
            for token, info in snapshot.items():
                # Eğer kayıtlı tenant_id bizimkisi ise
                if info.get('tenant_id') == tid:
                    # Platform kontrolü (iOS vs Diğerleri)
                    ua = info.get('userAgent', '')
                    platform = info.get('platform', '')
                    
                    is_ios = False
                    if re.search(r'iPhone|iPad|iPod', ua, re.IGNORECASE):
                        is_ios = True
                    elif re.search(r'iPhone|iPad|iPod', platform, re.IGNORECASE):
                        is_ios = True
                    # iPad on Desktop Mode Check (MacIntel + Touch) - UserAgent genelde Macintosh olur ama ayırt etmek zor.
                    # Şimdilik standart iOS user agent kontrolü yeterli.
                    
                    if is_ios:
                        tokens_ios.append(token)
                    else:
                        tokens_std.append(token)
                        
                    keys_to_del.append(token)
            
            topic_std = f'gundem_std_{tid}'
            topic_ios = f'gundem_ios_{tid}'

            if tokens_std:
                # Standart Topic'e abone yap, iOS Topic'ten çıkar (Göç durumu için)
                try:
                    messaging.subscribe_to_topic(tokens_std, topic_std)
                    messaging.unsubscribe_from_topic(tokens_std, topic_ios)
                except: pass

            if tokens_ios:
                # iOS Topic'e abone yap, Standart Topic'ten çıkar
                try:
                    messaging.subscribe_to_topic(tokens_ios, topic_ios)
                    messaging.unsubscribe_from_topic(tokens_ios, topic_std)
                except: pass
                
            # İşlenenleri Sil
            if keys_to_del:
                for k in keys_to_del:
                    try: db.reference(f'abone_bekleyenler/{k}').delete()
                    except: pass
                    
                # Log (Opsiyonel)
                # print(f"{len(tokens_to_sub)} yeni cihaz abone yapıldı.")
                
    except Exception as e:
        # Hata durumunda sessiz kal veya logla
        pass

# Geçmişi Yükle (Sadece bir kere)
if st.session_state.tenant_id and not st.session_state.db_history_loaded:
    try:
        ref_h = db.reference(f'tenants/{st.session_state.tenant_id}/gundem').order_by_key().limit_to_last(100)
        snapshot_h = ref_h.get()
        if snapshot_h:
            for key, val in snapshot_h.items():
                if 'haber' in val:
                    st.session_state.raporlanan_ozetler.append(val['haber'])
    except: pass
    st.session_state.db_history_loaded = True

if not st.session_state.tenant_id:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        img_b64 = get_img_as_base64("ikon.png")
        if img_b64:
            st.markdown(f"""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 20px;">
                    <img src="data:image/png;base64,{img_b64}" style="width: 80px; margin-bottom: 10px;">
                    <h3 style="text-align: center; margin: 0;">Kurumsal Giriş</h3>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<h3 style='text-align: center;'>Kurumsal Giriş</h3>", unsafe_allow_html=True)

        kurum_adi = st.text_input("Kurum Adı")
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap", use_container_width=True):
            if kurum_adi and password:
                tid, err = login_kurumsal(kurum_adi, password)
                if tid:
                    st.session_state.tenant_id = tid
                    st.rerun()
                else: st.error(err)
            else: st.warning("Lütfen alanları doldurunuz.")
    st.stop()

# Giriş başarılı ise bekleyen aboneleri işle (Her seferinde değil, sayaçla)
if 'abone_check_counter' not in st.session_state:
    st.session_state.abone_check_counter = 0

st.session_state.abone_check_counter += 1
if st.session_state.abone_check_counter % 5 == 0:
    bekleyen_aboneleri_isle(st.session_state.tenant_id)

# ==========================================
# 🛠️ FONKSİYONLAR
# ==========================================

def render_archive():
    st.divider()
    st.subheader("🗄️ Arşiv")

    try:
        ref = db.reference(f'tenants/{st.session_state.tenant_id}/gundem')
        snap = ref.get()
        if snap:
            keys = list(snap.keys())
            keys.reverse()
            tabs = st.tabs(["Gündem", "Politika", "Ekonomi", "Spor"])
            for i, cat in enumerate(["Gündem", "Politika", "Ekonomi", "Spor"]):
                with tabs[i]:
                    c = 0
                    for k in keys:
                        val = snap[k]
                        if val.get('kategori', 'Gündem') == cat or (cat=="Gündem" and val.get('kategori') not in ["Politika","Ekonomi","Spor"]):
                            with st.expander(f"{val['zaman']} - {val['haber'][:50]}..."):
                                st.write(val['haber'])
                                st.markdown(val.get('kaynaklar',''), unsafe_allow_html=True)
                            c+=1
                    if c==0: st.info("Veri yok.")
    except: pass

def firebase_bildirim_gonder(ozet, kaynaklar_html, kategori="Gündem", baslik_on_eki="🔥 Gündem"):
    tid = st.session_state.tenant_id
    tam_baslik = baslik_on_eki 
    
    veri = {
        "zaman": datetime.now().strftime("%H:%M"), 
        "tarih": datetime.now().strftime("%d.%m.%Y"), 
        "haber": ozet, 
        "kaynaklar": kaynaklar_html,
        "kategori": kategori,
        "baslik": tam_baslik
    }
    try: 
        db.reference(f'tenants/{tid}/gundem').push().set(veri)
    except: pass

    try:
        topic_std = f'gundem_std_{tid}'
        topic_ios = f'gundem_ios_{tid}'
        
        messaging.send(messaging.Message(
            data={"haber_baslik": tam_baslik, "haber_ozet": ozet, "title": tam_baslik, "body": ozet, "click_action": PWA_URL, "url": PWA_URL},
            android=messaging.AndroidConfig(priority="high", ttl=3600),
            webpush=messaging.WebpushConfig(headers={"Urgency": "high"}),
            topic=topic_std
        ))
        messaging.send(messaging.Message(
            notification=messaging.Notification(title=tam_baslik, body=ozet),
            data={"haber_baslik": tam_baslik, "haber_ozet": ozet, "prevent_duplicate": "true", "url": PWA_URL},
            topic=topic_ios,
            webpush=messaging.WebpushConfig(headers={"Urgency": "high"})
        ))
    except: pass

# Chrome temizle fonksiyonu KALDIRILDI (Multi-tenant çakışması için)

def tarayiciyi_baslat():
    if st.session_state.driver is None:
        # Her tenant için ayrı profil
        tid = st.session_state.tenant_id
        profile_path = os.path.join(os.getcwd(), f"ozel_twitter_profili_{tid}")
        if not os.path.exists(profile_path): os.makedirs(profile_path)
        
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        try:
            driver = uc.Chrome(options=options, user_data_dir=profile_path, use_subprocess=True)
            st.session_state.driver = driver
            return driver
        except Exception as e:
            if "This version of ChromeDriver only supports Chrome version" in str(e):
                try:
                    match = re.search(r"Current browser version is\s+(\d+)", str(e))
                    if match:
                        main_version = int(match.group(1))
                        driver = uc.Chrome(options=options, user_data_dir=profile_path, use_subprocess=True, version_main=main_version)
                        st.session_state.driver = driver
                        return driver
                except Exception as e2:
                    st.error(f"Tarayıcı başlatılamadı (Sürüm düzeltme başarısız): {e2}")
                    st.stop()

            st.error(f"Tarayıcı hatası: {e}"); st.stop()
    return st.session_state.driver

def oturum_kontrol(driver):
    try:
        driver.get("https://x.com/home")
        time.sleep(4)
        driver.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
        return True
    except: return False

def cop_tweet_kontrol(metin):
    cop = ["günaydın", "iyi geceler", "merhaba", "selam", "hayırlı cumalar", "takip", "gt", "beğeni"]
    return len(metin) < 15 or any(k in metin.lower() for k in cop)

def metin_on_isleme(metin):
    metin = re.sub(r'^(SON DAKİKA|FLAŞ|GELİŞME|ÖZEL HABER|DİKKAT|UYARI|GÜNDEM)\s*[|:!-]\s*', '', metin, flags=re.IGNORECASE)
    metin = re.sub(r'^[A-ZİĞÜŞÖÇ\s]+\s*[|]\s*', '', metin)
    return metin

def tweet_yakala(driver, limit=1):
    veriler = []
    try:
        # Scroll işlemleri (İnsan taklidi için random sleep)
        for _ in range(4): 
            driver.execute_script("window.scrollBy(0, 1500);")
            time.sleep(random.uniform(0.7, 1.5)) 
        articles = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]')
        if not articles: articles = driver.find_elements(By.TAG_NAME, "article")
        for article in articles:
            if len(veriler) >= limit: break
            try:
                tweet_text = article.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]').text
                try:
                    lnk = article.find_element(By.TAG_NAME, "time").find_element(By.XPATH, "..").get_attribute("href")
                except: lnk = "link_yok"
                own = lnk.split("/")[3] if "/" in lnk else "bilinmeyen"
                
                if not cop_tweet_kontrol(tweet_text):
                    veriler.append({"hesap": own, "metin": tweet_text, "link": lnk})
            except: continue
    except: pass
    return veriler

def haber_metni_olustur_groq(grup):
    client = Groq(api_key=GROQ_API_KEY)
    text = "\\n- ".join([f"@{t['hesap']}: {t['metin']}" for t in grup])
    prompt = f"""
    Aşağıdaki tweetleri tarafsız haber diliyle özetle. Kategori seç: Politika, Ekonomi, Spor, Gündem.
    Tweetler: {text}
    Çıktı JSON olsun: {{"ozet": "...", "kategori": "..."}}
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=250, response_format={"type": "json_object"}
        )
        j = json.loads(completion.choices[0].message.content)
        return j.get("ozet", grup[0]['metin']), j.get("kategori", "Gündem")
    except: return grup[0]['metin'], "Gündem"

def semantik_analiz(tweetler, threshold=0.35):
    if len(tweetler) < 2: return []
    metinler = [metin_on_isleme(t['metin']) for t in tweetler]
    try:
        vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2,4))
        mtx = vec.fit_transform(metinler)
        sim = cosine_similarity(mtx, mtx)
    except: return []

    gruplar = []
    used = set()
    for i in range(len(tweetler)):
        if i in used: continue
        grup = [tweetler[i]]
        used.add(i)
        for j in range(i+1, len(tweetler)):
            if j in used: continue
            if sim[i][j] > threshold:
                grup.append(tweetler[j])
                used.add(j)
        
        uniq = set(t['hesap'] for t in grup)
        if len(uniq) >= 2 or len(grup) >= 2:
            gruplar.append(grup)
    return gruplar

# ==========================================
# 🖥️ ARAYÜZ (ORIGINAL LAYOUT)
# ==========================================

img_b64 = get_img_as_base64("ikon.png")
if img_b64:
    st.markdown(f'<div style="display:flex;align-items:center;margin-bottom:20px;"><img src="data:image/png;base64,{img_b64}" style="width:50px;margin-right:15px;border-radius:10px;"><h1>X Gündem Takibi</h1></div><hr>', unsafe_allow_html=True)
else: st.title("X Gündem Takibi"); st.markdown("---")

with st.sidebar:
    st.header("⚙️ Ayarlar")
    st.success(f"Giriş: {st.session_state.tenant_id[:5]}...")
    
    tarama_tipi = st.radio("Yöntem", ["Kullanıcı Listesi", "Twitter Liste URL"])
    if tarama_tipi == "Kullanıcı Listesi":
        hedef_veri = st.text_area("Hesaplar (Virgülle)", placeholder="elonmusk, nasa")
    else:
        hedef_veri = st.text_input("Liste URL", placeholder="https://x.com/i/lists/...")
    
    ai_aktif = st.checkbox("🤖 AI ile Haber Yaz", value=True)
    dakika = st.slider("Tarama Sıklığı (dk)", 1, 60, 1)
    
    if st.button("▶️ BAŞLAT", type="primary"):
        st.session_state.is_running = True
        st.session_state.session_checked = False
        st.rerun()
    
    if st.button("⏹️ DURDUR"):
        st.session_state.is_running = False
        if st.session_state.driver:
            st.session_state.driver.quit()
            st.session_state.driver = None
        st.rerun()
        
    if st.button("Çıkış Yap"):
        st.session_state.tenant_id = None
        st.rerun()

    st.markdown("---")
    with st.expander("🔑 Şifre Değiştirme Talebi"):
        new_tenant_pass = st.text_input("Yeni Kurum Şifresi", type="password")
        if st.button("Talep Gönder"):
            if new_tenant_pass:
                try:
                    req_ref = db.reference(f'password_requests/{st.session_state.tenant_id}')
                    req_ref.set({
                        "new_password_hash": hash_password(new_tenant_pass),
                        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    st.success("Şifre değiştirme talebiniz yöneticiye iletildi.")
                except Exception as e:
                    st.error(f"Hata: {e}")
            else:
                st.warning("Lütfen yeni şifre giriniz.")

    st.markdown("---")
    st.warning("⚠️ Tehlikeli Bölge")
    if st.button("🗑️ Tüm Verilerimi Sil"):
        try:
            db.reference(f'tenants/{st.session_state.tenant_id}/gundem').delete()
            st.session_state.gordugum_linkler = set()
            st.session_state.raporlanan_ozetler = []
            st.success("Tüm verileriniz silindi.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Silme hatası: {e}")

    st.divider()
    st.header("👥 Çalışan Yönetimi")
    
    with st.expander("➕ Personel Ekle"):
        new_user = st.text_input("Kullanıcı Adı", key="new_user_input")
        new_pass = st.text_input("Şifre", type="password", key="new_pass_input")
        if st.button("Kaydet", key="save_user_btn"):
            if new_user and new_pass:
                try:
                    ref_user = db.reference(f'calisanlar/{new_user}')
                    if ref_user.get():
                        st.error("Bu kullanıcı adı kullanımda!")
                    else:
                        ref_user.set({
                            "sifre": new_pass,
                            "tenant_id": st.session_state.tenant_id
                        })
                        st.success(f"Personel eklendi: {new_user}")
                        time.sleep(1)
                        st.rerun()
                except Exception as e: st.error(f"Hata: {e}")
            else: st.warning("Kullanıcı adı ve şifre giriniz.")

    st.subheader("Mevcut Personeller")
    try:
        # Index hatasını aşmak için tümünü çekip Python'da filtreliyoruz
        all_calisanlar = db.reference('calisanlar').get()
        if all_calisanlar:
            # Sadece tenant_id eşleşenleri filtrele
            filtered_calisanlar = {k: v for k, v in all_calisanlar.items() if v.get('tenant_id') == st.session_state.tenant_id}
            
            if filtered_calisanlar:
                for k, v in filtered_calisanlar.items():
                    with st.expander(f"👤 {k}"):
                        new_u_name = st.text_input("Kullanıcı Adı", value=k, key=f"edit_user_{k}")
                        new_u_pass = st.text_input("Yeni Şifre (Değişmeyecekse boş bırak)", type="password", key=f"edit_pass_{k}")
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("Güncelle", key=f"upd_{k}"):
                                try:
                                    # Sadece şifre değiştiyse
                                    if new_u_name == k:
                                        if new_u_pass:
                                            db.reference(f'calisanlar/{k}').update({'sifre': new_u_pass})
                                            st.success("Şifre güncellendi!")
                                        else:
                                            st.info("Değişiklik yapılmadı.")
                                            
                                    # Kullanıcı adı değiştiyse (Yeni kayıt oluştur, eskisini sil)
                                    else:
                                        # Yeni ad dolu mu?
                                        check_ref = db.reference(f'calisanlar/{new_u_name}')
                                        if check_ref.get():
                                            st.error("Bu kullanıcı adı zaten kullanımda!")
                                        else:
                                            pass_to_save = new_u_pass if new_u_pass else v.get('sifre')
                                            
                                            # Yeniyi kaydet
                                            check_ref.set({
                                                'sifre': pass_to_save,
                                                'tenant_id': st.session_state.tenant_id
                                            })
                                            # Eskiyi sil
                                            db.reference(f'calisanlar/{k}').delete()
                                            st.success(f"Kullanıcı adı güncellendi: {new_u_name}")
                                            time.sleep(1)
                                            st.rerun()
                                except Exception as e: st.error(f"Hata: {e}")
                        
                        with col_b:
                            if st.button("Sil 🗑️", key=f"del_{k}"):
                                db.reference(f'calisanlar/{k}').delete()
                                st.rerun()

            else: st.info("Kayıtlı personel yok.")
        else: st.info("Kayıtlı personel yok.")
    except Exception as e: st.error(f"Veri çekilemedi: {e}")

# --- ÇALIŞMA ALANI ---
if st.session_state.is_running:
    driver = tarayiciyi_baslat()
    wait = WebDriverWait(driver, 15)
    
    if not st.session_state.session_checked:
        if not oturum_kontrol(driver):
            st.warning("⚠️ X oturumu açık değil! Açılan pencerede giriş yapın.")
            time.sleep(10)
            st.rerun()
        else:
            st.session_state.session_checked = True
        
    # Eski sistemdeki gibi anlık durum çubuğu
    status = st.status("Analiz sürüyor...", expanded=True)
    
    # 1. Veri Topla
    toplanan = []
    if tarama_tipi == "Kullanıcı Listesi":
        accs = [x.strip() for x in hedef_veri.split(",") if x.strip()]
        for acc in accs:
            status.write(f"🔍 @{acc} taranıyor...")
            driver.get(f"https://x.com/{acc}")
            time.sleep(1.5)
            toplanan.extend(tweet_yakala(driver, limit=10))
    else:
        status.write(f"🔗 Liste taranıyor...")
        driver.get(hedef_veri)
        time.sleep(2)
        toplanan.extend(tweet_yakala(driver, limit=25))
    
    # Yeni Tweetleri Havuza Ekle (Mükerrer Kontrolü ile)
    for t in toplanan:
        # Eğer buffer'da bu link yoksa ekle
        if not any(b['link'] == t['link'] for b in st.session_state.tweet_buffer):
            # Zaman damgası ekle (Buffer temizliği için)
            t['timestamp'] = time.time()
            st.session_state.tweet_buffer.append(t)
    
    # Havuz Temizliği (Son 20 dakika veya 150 tweet)
    simdiki_zaman = time.time()
    st.session_state.tweet_buffer = [
        t for t in st.session_state.tweet_buffer 
        if (simdiki_zaman - t.get('timestamp', 0)) < 1200 # 20 dakika (1200 sn)
    ][-150:] # Maksimum 150 tweet tut
    
    status.write(f"📊 Havuzdaki {len(st.session_state.tweet_buffer)} tweet analiz ediliyor...")
    
    # 2. Analiz (Sadece yeni toplananlar değil, tüm havuz analiz edilir)
    gruplar = semantik_analiz(st.session_state.tweet_buffer)
    
    yeni = False
    if gruplar:
        for grup in gruplar:
            # Grup içindeki linklerin kaçı daha önce raporlandı?
            grup_linkleri = set(t['link'] for t in grup)
            raporlananlar = st.session_state.raporlanan_linkler
            
            # Eğer grubun %50'sinden fazlası zaten raporlanmışsa bu grubu atla (Eski haberin güncellemesi)
            cakisma = len(grup_linkleri.intersection(raporlananlar))
            if cakisma > 0 and (cakisma / len(grup_linkleri)) > 0.5:
                continue

            if any(t['link'] not in st.session_state.gordugum_linkler for t in grup):
                ozet = grup[0]['metin']
                kat = "Gündem"
                if ai_aktif: ozet, kat = haber_metni_olustur_groq(grup)
                
                # Duplicate Check (Metin Bazlı - İkincil Kontrol)
                zaten_var = False
                
                def temizle(metin):
                    # Küçük harfe çevir, noktalama kaldır, kelimeleri 5 harfe kadar kısalt (stemming-lite)
                    words = re.sub(r'[^\w\s]', '', metin.lower()).split()
                    return set([w[:5] for w in words])
                
                s1_clean = temizle(ozet)
                
                for r in st.session_state.raporlanan_ozetler:
                    # 1. Yöntem: Kelime Kökü Benzerliği (Jaccard)
                    s2_clean = temizle(r)
                    if s1_clean and s2_clean:
                        jaccard = len(s1_clean & s2_clean) / len(s1_clean | s2_clean)
                        if jaccard > 0.4: 
                            zaten_var = True; break
                    
                    # 2. Yöntem: Karakter Dizisi Benzerliği (SequenceMatcher)
                    # Kelime sırası farklı olsa bile genel metin benzerliğini yakalar
                    if SequenceMatcher(None, ozet, r).ratio() > 0.6:
                        zaten_var = True; break
                
                if not zaten_var:
                    yeni = True
                    links = "".join([f"<li><small>@{t['hesap']}: {t['metin'][:80]}... <a href='{t['link']}'>Git</a></small></li>" for t in grup])
                    firebase_bildirim_gonder(ozet, links, kat)
                    
                    # Linkleri raporlandı olarak işaretle
                    for t in grup: 
                        st.session_state.gordugum_linkler.add(t['link'])
                        st.session_state.raporlanan_linkler.add(t['link'])
                        
                    st.session_state.raporlanan_ozetler.append(ozet)
                    
                    st.success(f"🔥 {kat}: {ozet[:60]}...")
                    if ai_aktif: st.info(ozet)
                    st.markdown(f"<ul>{links}</ul>", unsafe_allow_html=True)
                    try: winsound.Beep(1000, 300)
                    except: pass

    if not yeni: status.update(label="Yeni gündem yok.", state="complete")
    else: status.update(label="Analiz tamamlandı.", state="complete")
    
    # Arşivi burada göster (Rerun öncesi)
    render_archive()
    
    # URL Rotasyonu ve İnsan Taklidi (Güvenlik İçin)
    safe_urls = ["https://x.com/explore", "https://x.com/home"]
    if random.random() < 0.3: # %30 ihtimalle araya güvenli sayfa sıkıştır
        try:
            safe_target = random.choice(safe_urls)
            status.write(f"🔄 Güvenlik rotasyonu: {safe_target}...")
            driver.get(safe_target)
            time.sleep(random.randint(5, 10))
        except: pass

    # Adaptif Bekleme (Jitter + Gece Modu)
    saat = datetime.now().hour
    if 0 <= saat < 6:
        bekleme_suresi = random.randint(60, 90) # Gece daha yavaş
    else:
        bekleme_suresi = random.randint(35, 65) # Gündüz normal ama değişken
        
    with st.empty():
        for i in range(bekleme_suresi, 0, -1):
            st.caption(f"⏳ Bekleniyor (Anti-Bot): {i} sn")
            time.sleep(1)
    st.rerun()

# --- ARŞİV (STATİK GÖSTERİM) ---
render_archive()
