import os
import time
import random
import re
import json
import threading
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from groq import Groq
from database import get_db_connection
import requests
from pywebpush import webpush, WebPushException

class TwitterScraperThread(threading.Thread):
    def __init__(self, tenant_id):
        super().__init__()
        self.tenant_id = tenant_id
        self.running = True
        self.driver = None
        self.tweet_buffer = []
        self.gordugum_linkler = set()
        self.raporlanan_linkler = set()
        self.raporlanan_ozetler = []

        # Load historical sumaries for dup checking
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT haber FROM haberler WHERE tenant_id=%s ORDER BY id DESC LIMIT 50", (self.tenant_id,))
            rows = cursor.fetchall()
            self.raporlanan_ozetler = [r['haber'] for r in rows]
            cursor.close()
            conn.close()

    def get_settings(self):
        conn = get_db_connection()
        settings = {'tarama_tipi': 'Kullanıcı Listesi', 'hedef_veri': '', 'ai_aktif': True, 'dakika': 1}
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM tarama_ayarlari WHERE tenant_id=%s", (self.tenant_id,))
            row = cursor.fetchone()
            if row: settings = row
            cursor.close()
            conn.close()
        return settings

    def stop(self):
        self.running = False
        if self.driver:
            try: self.driver.quit()
            except: pass
            self.driver = None

    def start_browser(self):
        profile_path = os.path.join(os.getcwd(), f"ozel_twitter_profili_{self.tenant_id}")
        if not os.path.exists(profile_path): os.makedirs(profile_path)

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        # Ubuntu desktop ortamı için headless DEĞİL (kullanıcı görsün istedi)

        try:
            self.driver = uc.Chrome(options=options, user_data_dir=profile_path, use_subprocess=True)
        except Exception as e:
            print(f"[{self.tenant_id}] Tarayıcı hatası: {e}")
            self.running = False

    def oturum_kontrol(self):
        try:
            if "x.com" not in self.driver.current_url:
                self.driver.get("https://x.com/home")
            WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']") or
                          d.find_element(By.CSS_SELECTOR, "div[data-testid='primaryColumn']")
            )
            return True
        except:
            return False

    def cop_tweet_kontrol(self, metin):
        cop = ["günaydın", "iyi geceler", "merhaba", "selam", "hayırlı cumalar", "takip", "gt", "beğeni"]
        return len(metin) < 15 or any(k in metin.lower() for k in cop)

    def metin_on_isleme(self, metin):
        metin = re.sub(r'^(SON DAKİKA|FLAŞ|GELİŞME|ÖZEL HABER|DİKKAT|UYARI|GÜNDEM)\s*[|:!-]\s*', '', metin, flags=re.IGNORECASE)
        metin = re.sub(r'^[A-ZİĞÜŞÖÇ\s]+\s*[|]\s*', '', metin)
        return metin

    def tweet_yakala(self, limit=1):
        veriler = []
        try:
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]') or
                              d.find_elements(By.TAG_NAME, "article")
                )
            except: return []

            for _ in range(3):
                self.driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(random.uniform(1.5, 2.5))

            articles = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]')
            if not articles: articles = self.driver.find_elements(By.TAG_NAME, "article")

            for article in articles:
                if len(veriler) >= limit: break
                try:
                    tweet_text = article.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]').text
                    try:
                        time_element = article.find_element(By.TAG_NAME, "time")
                        lnk = time_element.find_element(By.XPATH, "..").get_attribute("href")
                    except: lnk = "link_yok"

                    own = lnk.split("/")[3] if "/" in lnk and len(lnk.split("/")) > 3 else "bilinmeyen"

                    if not self.cop_tweet_kontrol(tweet_text):
                        veriler.append({"hesap": own, "metin": tweet_text, "link": lnk})
                except: continue
        except: pass
        return veriler

    def haber_metni_olustur_groq(self, grup):
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
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

    def semantik_analiz(self, tweetler, threshold=0.35):
        if len(tweetler) < 2: return []
        metinler = [self.metin_on_isleme(t['metin']) for t in tweetler]
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

    def save_and_notify(self, ozet, kaynaklar_html, kategori):
        zaman = datetime.now().strftime("%H:%M")
        tarih = datetime.now().strftime("%d.%m.%Y")
        baslik = f"🔥 {kategori}"

        # Save to MySQL
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO haberler (tenant_id, zaman, tarih, haber, kaynaklar, kategori, baslik)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (self.tenant_id, zaman, tarih, ozet, kaynaklar_html, kategori, baslik))
            conn.commit()
            cursor.close()
            conn.close()

        # Send Web Push Notifications
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM push_subscriptions WHERE tenant_id=%s", (self.tenant_id,))
            subs = cursor.fetchall()

            private_key = os.getenv("VAPID_PRIVATE_KEY")
            claims = {"sub": os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")}

            payload = json.dumps({
                "title": baslik,
                "body": ozet,
                "url": "/"
            })

            invalid_subs = []
            for sub in subs:
                subscription_info = {
                    "endpoint": sub['endpoint'],
                    "keys": {
                        "p256dh": sub['p256dh'],
                        "auth": sub['auth']
                    }
                }
                try:
                    webpush(
                        subscription_info=subscription_info,
                        data=payload,
                        vapid_private_key=private_key,
                        vapid_claims=claims
                    )
                except WebPushException as ex:
                    if ex.response and ex.response.status_code in [404, 410]:
                        invalid_subs.append(sub['id'])
                    else:
                        print(f"[{self.tenant_id}] WebPush Hatası: {ex}")
                except Exception as e:
                    print(f"[{self.tenant_id}] WebPush Beklenmeyen Hata: {e}")

            # Geçersiz/silinmiş abonelikleri DB'den temizle
            if invalid_subs:
                format_strings = ','.join(['%s'] * len(invalid_subs))
                cursor.execute(f"DELETE FROM push_subscriptions WHERE id IN ({format_strings})", tuple(invalid_subs))
                conn.commit()

            cursor.close()
            conn.close()
            print(f"[{self.tenant_id}] Bildirim gönderildi: {ozet[:30]}...")


    def run(self):
        self.start_browser()
        if not self.driver: return

        while self.running:
            settings = self.get_settings()
            if not self.oturum_kontrol():
                print(f"[{self.tenant_id}] Lütfen X oturumu açın.")
                time.sleep(15)
                continue

            toplanan = []
            if settings.get('tarama_tipi') == "Kullanıcı Listesi":
                accs = [x.strip() for x in settings.get('hedef_veri', '').split(",") if x.strip()]
                for acc in accs:
                    if not self.running: break
                    self.driver.get(f"https://x.com/{acc}")
                    time.sleep(3)
                    toplanan.extend(self.tweet_yakala(limit=10))
            else:
                url = settings.get('hedef_veri', '')
                if url:
                    self.driver.get(url)
                    time.sleep(4)
                    toplanan.extend(self.tweet_yakala(limit=25))

            # Buffer update
            for t in toplanan:
                if not any(b['link'] == t['link'] for b in self.tweet_buffer):
                    t['timestamp'] = time.time()
                    self.tweet_buffer.append(t)

            simdiki_zaman = time.time()
            self.tweet_buffer = [t for t in self.tweet_buffer if (simdiki_zaman - t.get('timestamp', 0)) < 1200][-150:]

            # Semantic Analysis
            gruplar = self.semantik_analiz(self.tweet_buffer)
            if gruplar:
                for grup in gruplar:
                    grup_linkleri = set(t['link'] for t in grup)
                    cakisma = len(grup_linkleri.intersection(self.raporlanan_linkler))
                    if cakisma > 0 and (cakisma / len(grup_linkleri)) > 0.5:
                        continue

                    if any(t['link'] not in self.gordugum_linkler for t in grup):
                        ozet = grup[0]['metin']
                        kat = "Gündem"
                        if settings.get('ai_aktif'):
                            ozet, kat = self.haber_metni_olustur_groq(grup)

                        # Duplicate check
                        def temizle(metin):
                            words = re.sub(r'[^\w\s]', '', metin.lower()).split()
                            return set([w[:5] for w in words])

                        s1_clean = temizle(ozet)
                        zaten_var = False
                        for r in self.raporlanan_ozetler:
                            s2_clean = temizle(r)
                            if s1_clean and s2_clean:
                                jaccard = len(s1_clean & s2_clean) / len(s1_clean | s2_clean)
                                if jaccard > 0.4: zaten_var = True; break
                            if SequenceMatcher(None, ozet, r).ratio() > 0.6:
                                zaten_var = True; break

                        if not zaten_var:
                            links = "".join([f"<li><small>@{t['hesap']}: {t['metin'][:80]}... <a href='{t['link']}' target='_blank'>Git</a></small></li>" for t in grup])
                            self.save_and_notify(ozet, links, kat)

                            for t in grup:
                                self.gordugum_linkler.add(t['link'])
                                self.raporlanan_linkler.add(t['link'])
                            self.raporlanan_ozetler.append(ozet)

            # Wait cycle
            saat = datetime.now().hour
            bekleme = random.randint(60, 90) if 0 <= saat < 6 else random.randint(35, 65)
            # Sleep in chunks to allow interruption
            for _ in range(bekleme):
                if not self.running: break
                time.sleep(1)

        self.stop()
