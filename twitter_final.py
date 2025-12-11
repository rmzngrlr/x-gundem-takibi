import streamlit as st
import time
import os
import random
import winsound
import requests
import base64
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from collections import Counter
from datetime import datetime

# --- YAPAY ZEKA KÜTÜPHANELERİ ---
from deep_translator import GoogleTranslator
from transformers import pipeline

# ==========================================
# ⚙️ SABİT AYARLAR
# ==========================================
SABIT_TG_TOKEN = "" 
SABIT_TG_ID = ""    
# ==========================================

st.set_page_config(page_title="X Gündem Takibi", page_icon="ikon.png", layout="wide")

# --- GÖRÜNTÜ TEMİZLİĞİ ---
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

# --- AI MODELİNİ YÜKLE ---
@st.cache_resource
def model_yukle():
    # Large modelde kalıyoruz (En zekisi)
    return pipeline("text2text-generation", model="google/flan-t5-large")

# --- YARDIMCI FONKSİYONLAR ---
def get_img_as_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

def telegram_gonder(token, chat_id, mesaj):
    if token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": mesaj, "parse_mode": "Markdown", "disable_web_page_preview": True}
            requests.post(url, json=payload, timeout=5)
        except:
            pass

# --- ZEKİ ANALİZ (LARGE + TEKRAR KORUMALI) ---
def haber_metni_olustur(tweetler, generator):
    try:
        translator = GoogleTranslator(source='auto', target='en')
        tr_translator = GoogleTranslator(source='en', target='tr')
        
        metin_havuzu = ""
        unique_tweets = set()
        sayac = 0
        
        for t in tweetler:
            try:
                # Large model CPU'yu yormasın diye max 6 tweet veriyoruz.
                if sayac >= 6: break
                
                if t['metin'] not in unique_tweets:
                    temiz_metin = t['metin'].replace("\n", " ").strip()
                    if len(temiz_metin) > 15: 
                        tweet_en = translator.translate(temiz_metin)
                        metin_havuzu += f"- {tweet_en} "
                        unique_tweets.add(t['metin'])
                        sayac += 1
            except: pass
            
        if not metin_havuzu:
            return "Veri yetersiz."

        prompt = (
            f"Summarize the text below into a single objective sentence. "
            f"Maintain the original tense. "
            f"Use ONLY the provided information. "
            f"Text: {metin_havuzu}"
        )

        sonuc = generator(prompt, 
                          max_length=120,
                          min_length=15, 
                          repetition_penalty=3.0,
                          no_repeat_ngram_size=3,
                          early_stopping=True,
                          do_sample=False)
                          
        ingilizce_yorum = sonuc[0]['generated_text']
        
        return tr_translator.translate(ingilizce_yorum)
        
    except Exception as e:
        return "Analiz oluşturulamadı."

# --- TARAYICI ---
def tarayiciyi_baslat():
    if st.session_state.driver is None:
        working_dir = os.getcwd()
        profile_path = os.path.join(working_dir, "ozel_twitter_profili")
        if not os.path.exists(profile_path):
            os.makedirs(profile_path)
        options = uc.ChromeOptions()
        options.add_argument("--disable-popup-blocking")
        driver = uc.Chrome(options=options, user_data_dir=profile_path, use_subprocess=True)
        st.session_state.driver = driver
        return driver
    return st.session_state.driver

def tarayiciyi_kapat():
    if st.session_state.driver:
        try: st.session_state.driver.quit()
        except: pass
        st.session_state.driver = None
        st.session_state.is_running = False
        st.session_state.giris_yapildi_mi = False

def kelime_analizi(tweet_listesi):
    yasakli = {"ve", "veya", "bir", "bu", "şu", "o", "de", "da", "ile", "için", "çok", "ama", "https", "t.co", "status", "replying", "twitter", "com", "net", "resim", "video", "the", "a", "to", "in", "of", "is", "are"}
    tum_kelimeler = []
    for item in tweet_listesi:
        words = item['metin'].lower().replace("\n", " ").split()
        temiz = set([w for w in words if w not in yasakli and len(w) > 2])
        tum_kelimeler.extend(list(temiz))
    sayac = Counter(tum_kelimeler)
    return {k: v for k, v in sayac.items() if v > 1}

# --- GLOBAL DEĞİŞKENLER ---
if 'driver' not in st.session_state:
    st.session_state.driver = None
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'yakalanan_tweetler' not in st.session_state:
    st.session_state.yakalanan_tweetler = [] 
if 'gordugum_linkler' not in st.session_state:
    st.session_state.gordugum_linkler = set()
if 'giris_yapildi_mi' not in st.session_state:
    st.session_state.giris_yapildi_mi = False

# --- ARAYÜZ ---
klasor_yolu = os.path.dirname(__file__)
resim_adi = "ikon.png" 
tam_resim_yolu = os.path.join(klasor_yolu, resim_adi)

if os.path.exists(tam_resim_yolu):
    img_base64 = get_img_as_base64(tam_resim_yolu)
    header_html = f"""
<div style="display: flex; align-items: center; margin-bottom: 15px;">
    <img src="data:image/png;base64,{img_base64}" style="width: 40px; height: 40px; margin-right: 15px; object-fit: contain;">
    <h1 style="margin: 0; padding: 0; font-size: 2.2rem; font-family: sans-serif; line-height: 1.2;">X Gündem Takibi</h1>
</div>
<hr style="margin-top: 5px; margin-bottom: 20px; border: 0; border-top: 1px solid #444;">
"""
    st.markdown(header_html, unsafe_allow_html=True)
else:
    st.title("🧠 X Gündem Takibi")
    st.markdown("---")

# --- SOL MENÜ ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    hesaplar = st.text_area("Takip Listesi", placeholder="Lütfen kullanıcı adlarını giriniz!", key="hesap_listesi")
    
    ai_aktif = st.checkbox("🤖 Yapay Zeka ile Özetle", value=True)
    
    dakika = st.slider("Tarama Sıklığı (Dakika)", 1, 60, 1)
    
    with st.expander("Telegram Bildirim Ayarları"):
        tg_token = st.text_input("Bot Token", value=SABIT_TG_TOKEN, type="password")
        tg_id = st.text_input("Chat ID", value=SABIT_TG_ID)
    
    st.divider()
    
    c1, c2 = st.columns(2)
    if c1.button("▶️ BAŞLAT", type="primary"):
        st.session_state.is_running = True
        st.rerun()
    if c2.button("⏹️ DURDUR"):
        tarayiciyi_kapat()
        st.stop()
    
    if st.button("🗑️ Arşivi Temizle"):
        st.session_state.yakalanan_tweetler = []
        st.session_state.gordugum_linkler = set()
        st.success("Temizlendi.")
        time.sleep(1)
        st.rerun()

# --- PROGRAM AKIŞI ---
if st.session_state.is_running:
    try:
        generator = model_yukle()
        driver = tarayiciyi_baslat()
        status = st.status("Sistem çalışıyor...", expanded=True)

        target_accounts = [x.strip() for x in hesaplar.split(",") if x.strip()]
        
        if not target_accounts:
            status.error("Lütfen takip edilecek hesapları giriniz!")
            st.stop()

        guncel_veriler = [] 
        bar = status.progress(0, "Veriler çekiliyor...")
        
        for i, acc in enumerate(target_accounts):
            time.sleep(random.uniform(2, 4))
            driver.get(f"https://twitter.com/{acc}")
            time.sleep(3)
            
            if i == 0 and "login" in driver.current_url:
                status.error("Giriş Yapılmamış! Lütfen tarayıcıda giriş yapın.")
                st.stop()

            tweet_data = {"hesap": acc, "metin": "", "link": ""}
            try:
                elm = driver.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]')
                tweet_data["metin"] = elm.text
                time_elm = driver.find_element(By.TAG_NAME, "time")
                tweet_data["link"] = time_elm.find_element(By.XPATH, "..").get_attribute("href")
                status.write(f"✅ {acc} alındı.")
            except:
                tweet_data["metin"] = "Veri yok"
            
            guncel_veriler.append(tweet_data)
            bar.progress((i + 1) / len(target_accounts))
            
        status.update(label="Gündem Analiz Ediliyor...", state="complete", expanded=False)
        
        valid_tweets = [t for t in guncel_veriler if t['metin'] != "Veri yok"]
        ortak_kelimeler = kelime_analizi(valid_tweets)
        
        st.subheader("📰 Gündem Raporu")
        
        if ortak_kelimeler:
            bulunanlar = sorted(list(ortak_kelimeler.keys()))
            
            st.error(f"🚨 TESPİT EDİLEN KONU: {bulunanlar}")
            
            yeni_veri_var = False
            for t in valid_tweets:
                if t['link'] not in st.session_state.gordugum_linkler:
                    yeni_veri_var = True
                    st.session_state.gordugum_linkler.add(t['link'])
            
            # GÜNCELLEME: Yeni veri varsa her türlü rapor oluştur ve KAYDET
            if yeni_veri_var:
                haber_metni = ""
                if ai_aktif:
                    with st.spinner("🤖 Haber metni oluşturuluyor..."):
                        haber_metni = haber_metni_olustur(valid_tweets, generator)
                else:
                    haber_metni = "⚠️ AI özetleme kapalı. Sadece konu tespiti ve kaynaklar listelenmiştir."

                html_kaynaklar = ""
                tg_linkler = ""
                for t in valid_tweets:
                    html_kaynaklar += f"<li style='margin-bottom: 5px; color: #BBB;'>@{t['hesap']} <a href='{t['link']}' target='_blank' style='color: #4DA6FF; text-decoration: none; font-size: 0.9em; margin-left:5px;'>(Tweeti Oku 🔗)</a></li>"
                    tg_linkler += f"🔹 {t['hesap']}: [Tweeti Gör]({t['link']})\n"

                kart_html = f"""
<div style="background-color: #262730; padding: 25px; border-radius: 12px; border: 1px solid #444; border-left: 6px solid #FF4B4B; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
    <div style="display: flex; align-items: center; margin-bottom: 15px;">
        <span style="font-size: 24px; margin-right: 10px;">🤖</span>
        <h3 style="color: #ffffff; margin: 0; font-family: sans-serif;">Gündem Özeti</h3>
    </div>
    <p style="font-size: 18px; color: #E0E0E0; line-height: 1.6; font-family: sans-serif; font-weight: 400; margin-bottom: 20px;">
        {haber_metni}
    </p>
    <div style="background-color: #1E1E1E; padding: 15px; border-radius: 8px;">
        <p style="font-size: 13px; color: #888; margin-top: 0; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;">Kaynaklar & Kanıtlar</p>
        <ul style="margin: 0; padding-left: 20px; list-style-type: square;">
            {html_kaynaklar}
        </ul>
    </div>
</div>
"""
                st.markdown(kart_html, unsafe_allow_html=True)
                
                # --- TELEGRAM & KAYIT ---
                tg_mesaj = f"🤖 *X GÜNDEM TAKİBİ*\n\n🔥 *Konu:* {bulunanlar}\n\n📝 *Haber:* {haber_metni}\n\n🔗 *Kaynaklar:*\n{tg_linkler}"
                telegram_gonder(tg_token, tg_id, tg_mesaj)

                # DÜZELTME: Konu aynı olsa bile yeni veri varsa LİSTEYE EKLE (Üzerine yazma)
                # Böylece geçmiş raporlarda akış görünür.
                kayit = {
                    "zaman": datetime.now().strftime("%H:%M"),
                    "baslik": f"Gündem: {bulunanlar}",
                    "haber": haber_metni,
                    "kaynaklar_html": html_kaynaklar
                }
                st.session_state.yakalanan_tweetler.insert(0, kayit)
                winsound.Beep(1000, 500)
                
                st.info(f"Gündem güncellendi ve Telegram'a iletildi: {bulunanlar}")

            else:
                st.info("Mevcut gündemde yeni bir gelişme yok.")
        else:
            st.success(f"Sakin, ortak bir gündem yok. ({datetime.now().strftime('%H:%M')})")

        st.divider()
        st.subheader("🗄️ Geçmiş Raporlar")
        
        # En sonuncusu (index 0) zaten yukarıda büyük kartta gösterildiği için
        # listede 2. sıradan (index 1) itibaren gösteriyoruz ki tekrar olmasın.
        if len(st.session_state.yakalanan_tweetler) > 1:
            for item in st.session_state.yakalanan_tweetler[1:]:
                with st.expander(f"⏰ {item['zaman']} - {item['baslik']}"):
                    st.write(item['haber'])
                    st.divider()
                    st.markdown(f"<ul>{item['kaynaklar_html']}</ul>", unsafe_allow_html=True)
        else:
            st.caption("Henüz arşivlenmiş eski rapor yok.")
        
        with st.empty():
            for s in range(dakika * 60, 0, -1):
                st.caption(f"⏳ Sonraki tarama: {s} sn")
                time.sleep(1)
        st.rerun()

    except Exception as e:
        st.error(f"Hata: {e}")
        time.sleep(10)
        st.rerun()
