import streamlit as st
import time
import os
import random
import winsound
import requests
import base64
import subprocess
import traceback
import string
import urllib.parse
import difflib # Gelişmiş isim düzeltme için
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

# --- YAPAY ZEKA KÜTÜPHANELERİ ---
from deep_translator import GoogleTranslator
from transformers import pipeline
from sentence_transformers import SentenceTransformer, util

# ==========================================
# ⚙️ SABİT AYARLAR
# ==========================================
SABIT_TG_TOKEN = "" 
SABIT_TG_ID = ""
    
# WHATSAPP AYARLARI (CallMeBot)
SABIT_WS_TEL = ""  
SABIT_WS_API = "" 
# ==========================================

st.set_page_config(page_title="X Gündem Takibi v2.60", page_icon="ikon.png", layout="wide")

# --- CSS VE GÖRÜNÜM ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .stDeployButton {display:none;}
            [data-testid="stHeaderActionElements"] {display: none !important;}
            h1 > a, h2 > a, h3 > a {display: none !important;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- TEMİZLİK FONKSİYONU ---
def chrome_temizle():
    try:
        if os.name == 'nt':
            subprocess.call("taskkill /F /IM chrome.exe /T", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            subprocess.call("taskkill /F /IM chromedriver.exe /T", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except: pass

# --- AI MODELLERİNİ YÜKLE ---
@st.cache_resource
def modelleri_yukle():
    summarizer = pipeline("text2text-generation", model="google/flan-t5-large")
    similarity_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return summarizer, similarity_model

# --- YARDIMCI FONKSİYONLAR ---
def get_img_as_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

def telegram_gonder(token, chat_id, mesaj):
    if token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": mesaj, "parse_mode": "HTML", "disable_web_page_preview": True}
            requests.post(url, json=payload, timeout=5)
        except: pass

def whatsapp_gonder(hedef, api_key, mesaj):
    if hedef and api_key:
        try:
            encoded_msg = urllib.parse.quote(mesaj)
            url = f"https://api.callmebot.com/whatsapp.php?phone={hedef}&text={encoded_msg}&apikey={api_key}"
            requests.get(url, timeout=10)
        except Exception as e:
            print(f"WhatsApp Hatası: {e}")

# --- GÜRÜLTÜ FİLTRESİ ---
def cop_tweet_kontrol(metin):
    cop_kelimeler = ["günaydın", "iyi geceler", "merhaba", "selam", "hayırlı cumalar", "iyi günler", "takip", "gt", "beğeni"]
    metin_lower = metin.lower()
    if len(metin) < 10: return True
    if any(k in metin_lower for k in cop_kelimeler): return True
    return False

# --- GÜNCELLENEN OTURUM VE TARAYICI KISMI ---
def tarayiciyi_baslat():
    if st.session_state.driver is None:
        chrome_temizle()
        time.sleep(1)
        
        working_dir = os.getcwd()
        profile_path = os.path.join(working_dir, "ozel_twitter_profili")
        if not os.path.exists(profile_path):
            os.makedirs(profile_path)
            
        options = uc.ChromeOptions()
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-notifications")
        options.add_argument("--start-maximized")
        # Headless mod KALDIRILDI, manuel girişe izin veriliyor.
        
        try:
            driver = uc.Chrome(options=options, user_data_dir=profile_path, use_subprocess=True)
            driver.set_page_load_timeout(60)
            st.session_state.driver = driver
            return driver
        except Exception as e:
            st.error(f"Tarayıcı hatası: {e}")
            st.stop()
            
    return st.session_state.driver

def oturum_kontrol(driver):
    """X ana sayfasına gider ve giriş yapılıp yapılmadığını denetler."""
    try:
        driver.get("https://x.com/home")
        time.sleep(4)
        # Home linki varsa oturum açıktır
        driver.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
        return True
    except:
        return False

# --- TWEET YAKALAMA (Aynen Korundu) ---
def tweet_yakala(driver, wait, limit=1):
    veriler = []
    try:
        for _ in range(4): 
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1.0) 

        articles = []
        try:
            articles = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "article")))
        except:
            articles = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]')
        
        count = 0
        for article in articles:
            if count >= limit: break
            
            tweet_text = "Veri yok"
            tweet_link = ""
            tweet_owner = "Bilinmiyor"
            
            try:
                tweet_text = article.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]').text
            except:
                try: tweet_text = article.text
                except: continue
            
            try:
                time_elm = article.find_element(By.TAG_NAME, "time")
                tweet_link = time_elm.find_element(By.XPATH, "..").get_attribute("href")
            except: pass

            try:
                if tweet_link:
                    parts = tweet_link.split("/")
                    if "status" in parts:
                        idx = parts.index("status")
                        tweet_owner = parts[idx-1]
                
                if tweet_owner == "Bilinmiyor":
                    user_elm = article.find_element(By.CSS_SELECTOR, 'div[data-testid="User-Name"]')
                    tweet_owner = user_elm.text.split("\n")[0]
            except: pass

            if tweet_text != "Veri yok" and len(tweet_text) > 3 and tweet_link:
                if not cop_tweet_kontrol(tweet_text):
                    veriler.append({"hesap": tweet_owner, "metin": tweet_text, "link": tweet_link})
                    count += 1
                
    except Exception:
        pass
    return veriler

# --- ANALİZ VE İSİM DÜZELTİCİ (v2.60 Aynen Korundu) ---
def semantik_gundem_analizi(tweetler, sim_model, threshold=0.50):
    if not tweetler or len(tweetler) < 2: return []

    def kelime_cakismasi_var_mi(t1, t2):
        stop_words = {"bir", "ve", "bu", "ile", "için", "çok", "ama", "de", "da", "daha", "en", "var", "yok", "mi", "mı", "ben", "sen", "o", "biz", "siz", "onlar", "diye", "gibi", "kadar", "olan", "olarak"}
        def temizle(metin): return metin.translate(str.maketrans('', '', string.punctuation)).lower().split()
        k1 = set(w for w in temizle(t1) if w not in stop_words and len(w) > 3)
        k2 = set(w for w in temizle(t2) if w not in stop_words and len(w) > 3)
        ortak = k1.intersection(k2)
        if len(ortak) >= 2: return True
        if any(len(w) > 6 for w in ortak): return True
        return False

    metinler = [t['metin'] for t in tweetler]
    embeddings = sim_model.encode(metinler, convert_to_tensor=True)
    cosine_scores = util.cos_sim(embeddings, embeddings)
    
    gruplar = []
    islenen_indexler = set()
    for i in range(len(tweetler)):
        if i in islenen_indexler: continue
        gecici_grup = [tweetler[i]]
        islenen_indexler.add(i)
        for j in range(i + 1, len(tweetler)):
            if j in islenen_indexler: continue
            score = cosine_scores[i][j]
            keyword_match = kelime_cakismasi_var_mi(tweetler[i]['metin'], tweetler[j]['metin'])
            if score > threshold or (score > 0.20 and keyword_match):
                gecici_grup.append(tweetler[j])
                islenen_indexler.add(j)
        farkli_hesaplar = set(t['hesap'] for t in gecici_grup)
        if len(farkli_hesaplar) >= 2 or len(gecici_grup) >= 3:
            gruplar.append(gecici_grup)
    return gruplar

def haber_metni_olustur(grup_tweetleri, generator):
    def akilli_isim_duzeltici(ozet_metni, kaynak_metni):
        ozel_noktalama = string.punctuation + "‘’“”'\""
        tr_map = str.maketrans('', '', ozel_noktalama)
        kaynak_kelimeler = kaynak_metni.split()
        kaynak_isim_sozlugu = {} 
        for k in kaynak_kelimeler:
            temiz_k = k.translate(tr_map)
            if len(temiz_k) > 2 and temiz_k[0].isupper():
                kaynak_isim_sozlugu[temiz_k.lower()] = temiz_k
        ozet_kelimeler = ozet_metni.split()
        yeni_ozet = []
        for kelime in ozet_kelimeler:
            temiz_kelime = kelime.translate(tr_map)
            if len(temiz_kelime) > 2 and temiz_kelime[0].isupper():
                kelime_lower = temiz_kelime.lower()
                if kelime_lower in kaynak_isim_sozlugu:
                    dogru_yazim = kaynak_isim_sozlugu[kelime_lower]
                    yeni_ozet.append(kelime.replace(temiz_kelime, dogru_yazim))
                else:
                    yakinlar = difflib.get_close_matches(kelime_lower, kaynak_isim_sozlugu.keys(), n=1, cutoff=0.70)
                    if yakinlar:
                        dogru_isim = kaynak_isim_sozlugu[yakinlar[0]]
                        yeni_ozet.append(kelime.replace(temiz_kelime, dogru_isim))
                    else: yeni_ozet.append(kelime)
            else: yeni_ozet.append(kelime)
        return " ".join(yeni_ozet)

    en_uzun_tweet = ""
    kaynak_full_text = " ".join([t['metin'] for t in grup_tweetleri])

    try:
        translator = GoogleTranslator(source='auto', target='en')
        tr_translator = GoogleTranslator(source='en', target='tr')
        metin_havuzu = ""
        unique_texts = set()
        for t in grup_tweetleri:
            temiz = t['metin'].replace("\n", " ").strip()
            if len(temiz) < 5: continue
            if len(temiz) > len(en_uzun_tweet): en_uzun_tweet = temiz
            if temiz not in unique_texts:
                try:
                    eng = translator.translate(temiz)
                    metin_havuzu += f"{eng}. " 
                    unique_texts.add(temiz)
                except: pass
        if not metin_havuzu: return en_uzun_tweet
        prompt = (f"Summarize these statements into a SINGLE, short, and concise news sentence. Text: {metin_havuzu}")
        sonuc = generator(prompt, max_length=80, min_length=10, repetition_penalty=3.0, no_repeat_ngram_size=3, early_stopping=True, do_sample=False)
        ingilizce_ozet = sonuc[0]['generated_text']
        try:
            ai_ozeti_tr = tr_translator.translate(ingilizce_ozet)
            if not ai_ozeti_tr or ai_ozeti_tr == ingilizce_ozet: return en_uzun_tweet 
            duzeltilmis_ozet = akilli_isim_duzeltici(ai_ozeti_tr, kaynak_full_text)
            return duzeltilmis_ozet
        except: return en_uzun_tweet 
    except: return en_uzun_tweet if en_uzun_tweet else "Özet oluşturulamadı."

# --- GLOBAL DURUMLAR VE ARAYÜZ ---
if 'driver' not in st.session_state: st.session_state.driver = None
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'arsiv' not in st.session_state: st.session_state.arsiv = [] 
if 'gordugum_linkler' not in st.session_state: st.session_state.gordugum_linkler = set()
if 'raporlanan_ozetler' not in st.session_state: st.session_state.raporlanan_ozetler = []

klasor_yolu = os.path.dirname(__file__)
tam_resim_yolu = os.path.join(klasor_yolu, "ikon.png")

if os.path.exists(tam_resim_yolu):
    img_base64 = get_img_as_base64(tam_resim_yolu)
    header_html = f'<div style="display: flex; align-items: center; margin-bottom: 20px;"><img src="data:image/png;base64,{img_base64}" style="width: 50px; height: 50px; margin-right: 15px; border-radius:10px;"><h1 style="margin: 0; padding: 0; font-size: 2.5rem;">X Gündem Takibi</h1></div><hr style="margin-top: 0px; margin-bottom: 20px;">'
    st.markdown(header_html, unsafe_allow_html=True)
else:
    st.title("X Gündem Takibi")
    st.markdown("---")

with st.sidebar:
    st.header("⚙️ Ayarlar")
    tarama_tipi = st.radio("Yöntem", ["Kullanıcı Listesi", "Twitter Liste URL"])
    hedef_veri = ""
    if tarama_tipi == "Kullanıcı Listesi":
        hedef_veri = st.text_area("Hesaplar (Virgülle)", placeholder="elonmusk, nasa")
    else:
        hedef_veri = st.text_input("Liste URL", placeholder="https://x.com/i/lists/...")
    ai_aktif = st.checkbox("🤖 Yapay Zeka ile Özetle", value=True)
    dakika = st.slider("Tarama Sıklığı (Dakika)", 1, 60, 1)
    st.divider()
    with st.expander("Bildirim Ayarları", expanded=True):
        tg_token = st.text_input("Bot Token", value=SABIT_TG_TOKEN, type="password")
        tg_id = st.text_input("Chat ID", value=SABIT_TG_ID)
        ws_hedef = st.text_input("Tel No", value=SABIT_WS_TEL)
        ws_api = st.text_input("API Key", value=SABIT_WS_API, type="password")
    
    c1, c2 = st.columns(2)
    if c1.button("▶️ BAŞLAT", type="primary"):
        st.session_state.is_running = True
        st.rerun()
    if c2.button("⏹️ DURDUR"):
        if st.session_state.driver:
            try: st.session_state.driver.quit()
            except: pass
            st.session_state.driver = None
        chrome_temizle()
        st.session_state.is_running = False
        st.stop()

if st.session_state.is_running:
    try:
        with st.spinner("Sistem Hazırlanıyor..."):
            summarizer, similarity_model = modelleri_yukle()
            driver = tarayiciyi_baslat()
            wait = WebDriverWait(driver, 15)

        if not oturum_kontrol(driver):
            st.warning("⚠️ X oturumu açık değil! Lütfen açılan Chrome penceresinde giriş yapın. Giriş yaptıktan sonra tarama başlayacaktır.")
            time.sleep(10)
            st.rerun()
        
        status = st.status("Analiz sürüyor...", expanded=True)
        toplanan_tweetler = []
        
        if tarama_tipi == "Kullanıcı Listesi":
            hesaplar = [x.strip() for x in hedef_veri.split(",") if x.strip()]
            prog = status.progress(0, "Profillere bakılıyor...")
            for i, acc in enumerate(hesaplar):
                driver.get(f"https://x.com/{acc}")
                tweets = tweet_yakala(driver, wait, limit=5) 
                if tweets: toplanan_tweetler.extend(tweets)
                time.sleep(random.uniform(2, 3.5)) 
                prog.progress((i+1)/len(hesaplar))
        else:
            driver.get(hedef_veri)
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(2)
            toplanan_tweetler = tweet_yakala(driver, wait, limit=15)

        gruplar = semantik_gundem_analizi(toplanan_tweetler, similarity_model, threshold=0.50)
        
        if gruplar:
            yeni_var = False
            for grup in gruplar:
                yeni_link_var_mi = any(t['link'] not in st.session_state.gordugum_linkler for t in grup)
                if yeni_link_var_mi:
                    ozet = haber_metni_olustur(grup, summarizer) if ai_aktif else grup[0]['metin']
                    zaten_raporlandi = False
                    if st.session_state.raporlanan_ozetler:
                        for eski_ozet in st.session_state.raporlanan_ozetler:
                            if ozet in eski_ozet or eski_ozet in ozet: zaten_raporlandi = True; break
                        if not zaten_raporlandi:
                            embeddings_yeni = similarity_model.encode([ozet], convert_to_tensor=True)
                            embeddings_eski = similarity_model.encode(st.session_state.raporlanan_ozetler, convert_to_tensor=True)
                            cosine_scores = util.cos_sim(embeddings_yeni, embeddings_eski)
                            if any(score > 0.82 for score in cosine_scores[0]): zaten_raporlandi = True

                    if not zaten_raporlandi:
                        yeni_var = True
                        for t in grup: st.session_state.gordugum_linkler.add(t['link'])
                        st.session_state.raporlanan_ozetler.append(ozet)
                        if len(st.session_state.raporlanan_ozetler) > 25: st.session_state.raporlanan_ozetler.pop(0)

                        html_k = "".join([f"<li><small>@{t['hesap']}: {t['metin'][:80]}... <a href='{t['link']}' target='_blank'>Link</a></small></li>" for t in grup])
                        st.success(f"🔥 Gündem: {ozet[:60]}...")
                        if ai_aktif: st.info(ozet)
                        st.markdown(f"<ul>{html_k}</ul>", unsafe_allow_html=True)
                        st.session_state.arsiv.insert(0, {"zaman": datetime.now().strftime("%H:%M"), "haber": ozet, "kaynak": html_k})
                        telegram_gonder(tg_token, tg_id, f"🤖 <b>X GÜNDEM</b>\n\n📝 {ozet}")
                        winsound.Beep(1000, 300)
            
            if not yeni_var: status.update(label="Yeni gelişme yok.", state="complete")
        else: status.update(label="Ortak gündem yok.", state="complete")

        st.divider()
        st.subheader("🗄️ Arşiv")
        if st.session_state.arsiv:
            for item in st.session_state.arsiv:
                with st.expander(f"⏰ {item['zaman']}"):
                    st.write(item['haber'])
                    st.markdown(item['kaynak'], unsafe_allow_html=True)
        
        with st.empty():
            for i in range(dakika * 60, 0, -1):
                st.caption(f"⏳ Sonraki tarama: {i} sn")
                time.sleep(1)
        st.rerun()

    except Exception as e:
        st.error(f"Hata: {e}")
        time.sleep(10)
        st.rerun()
