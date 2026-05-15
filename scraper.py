import os
import time
import random
import re
import json
import sys
import threading
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from groq import Groq
from database import get_db_connection
import requests
from pywebpush import webpush, WebPushException

uc = None
By = None
WebDriverWait = None

def ensure_selenium_imports():
    global uc, By, WebDriverWait
    if uc is None:
        import undetected_chromedriver as _uc
        from selenium.webdriver.common.by import By as _By
        from selenium.webdriver.support.ui import WebDriverWait as _WebDriverWait
        uc = _uc
        By = _By
        WebDriverWait = _WebDriverWait

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
        self._last_login_warning_time = 0
        self.next_scan_time = 0

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
        settings = {'tarama_tipi': 'Kullanıcı Listesi', 'hedef_veri': '', 'ai_aktif': True}
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
        ensure_selenium_imports()
        profile_path = os.path.join(os.getcwd(), f"chrome_profile_{self.tenant_id}")
        if not os.path.exists(profile_path): os.makedirs(profile_path)

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-session-crashed-bubble")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # Kullanıcının fiziksel Chrome görmesi istendiği için headless kaldırıldı
        # Ancak X11/Wayland çökmelerini engellemek için DISPLAY ayarı yapılır
        if "DISPLAY" not in os.environ:
            os.environ["DISPLAY"] = ":0"

        # Olası Chrome binary yollarını bul
        binary_location = None
        common_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium"
        ]
        for path in common_paths:
            if os.path.exists(path):
                binary_location = path
                break

        print(f"[{self.tenant_id}] Chrome driver baslatiliyor... (Bulunan binary: {binary_location})", flush=True)
        try:
            if binary_location:
                self.driver = uc.Chrome(options=options, browser_executable_path=binary_location, user_data_dir=profile_path, use_subprocess=True)
            else:
                self.driver = uc.Chrome(options=options, user_data_dir=profile_path, use_subprocess=True)
            print(f"[{self.tenant_id}] Chrome basariyla baslatildi.", flush=True)
        except Exception as e:
            if "This version of ChromeDriver only supports Chrome version" in str(e):
                try:
                    match = re.search(r"Current browser version is\s+(\d+)", str(e))
                    if match:
                        main_version = int(match.group(1))
                        print(f"[{self.tenant_id}] Surum uymusmazligi. Sürüm {main_version} deneniyor...", flush=True)
                        # Re-create options as it cannot be reused
                        new_options = uc.ChromeOptions()
                        new_options.add_argument("--start-maximized")
                        new_options.add_argument("--disable-notifications")
                        # Kullanıcının fiziksel Chrome görmesi istendiği için headless kaldırıldı
                        if binary_location:
                            self.driver = uc.Chrome(options=new_options, browser_executable_path=binary_location, user_data_dir=profile_path, use_subprocess=True, version_main=main_version)
                        else:
                            self.driver = uc.Chrome(options=new_options, user_data_dir=profile_path, use_subprocess=True, version_main=main_version)
                        print(f"[{self.tenant_id}] Chrome (Fallback) basariyla baslatildi.", flush=True)
                        return
                except Exception as e2:
                    print(f"[{self.tenant_id}] Tarayıcı başlatılamadı (Sürüm düzeltme başarısız): {e2}", flush=True)

            print(f"[{self.tenant_id}] Tarayıcı hatası: {e}", flush=True)
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

    def tweet_yakala(self, limit=50):
        veriler = []
        try:
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]') or
                              d.find_elements(By.TAG_NAME, "article")
                )
            except: return []

            bulunan_linkler = set()
            eski_sayaci = 0
            # Smart scrolling: En fazla 15 kez kaydır. Eğer peş peşe 3 kaydırmada hep eski (gördüğümüz) linkleri görürsek dur.
            for scroll_tur in range(15):
                articles = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]')
                if not articles: articles = self.driver.find_elements(By.TAG_NAME, "article")

                yeni_bulundu = False
                for article in articles:
                    if len(veriler) >= limit: break
                    try:
                        try:
                            time_element = article.find_element(By.TAG_NAME, "time")
                            lnk = time_element.find_element(By.XPATH, "..").get_attribute("href")
                        except: lnk = "link_yok"

                        if lnk in bulunan_linkler:
                            continue

                        bulunan_linkler.add(lnk)

                        if lnk != "link_yok" and lnk not in self.gordugum_linkler:
                            yeni_bulundu = True

                        tweet_text = article.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]').text
                        own = lnk.split("/")[3] if "/" in lnk and len(lnk.split("/")) > 3 else "bilinmeyen"

                        if not self.cop_tweet_kontrol(tweet_text):
                            veriler.append({"hesap": own, "metin": tweet_text, "link": lnk})
                    except: continue

                if len(veriler) >= limit: break

                if not yeni_bulundu:
                    eski_sayaci += 1
                else:
                    eski_sayaci = 0

                # Eğer peş peşe 3 kaydırmada hiç yeni link bulamadıysa, geçmişe ulaşmışız demektir, çıkabiliriz.
                if eski_sayaci >= 3:
                    break

                self.driver.execute_script("window.scrollBy(0, 1500);")
                time.sleep(random.uniform(1.5, 2.5))

        except Exception as e:
            pass

        return veriler

    def haber_metni_olustur_groq(self, grup):
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        text = "\n- ".join([f"@{t['hesap']}: {t['metin']}" for t in grup])
        prompt = f"""
        Aşağıdaki tweetleri tarafsız haber diliyle özetle. Kategorilerden SADECE BİRİNİ seç: Politika, Ekonomi, Spor, Gündem.
        Tweetler: {text}
        Çıktı SADECE geçerli bir JSON olmalıdır. Ekstra hiçbir metin ekleme: {{"ozet": "...", "kategori": "..."}}
        """
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=250, response_format={"type": "json_object"}
            )
            content = completion.choices[0].message.content

            # Markdown block fallback
            content = content.replace("```json", "").replace("```", "").strip()

            j = json.loads(content)

            # Kategori Doğrulama
            kat = j.get("kategori", "Gündem").strip().capitalize()
            if kat not in ["Politika", "Ekonomi", "Spor", "Gündem"]:
                kat = "Gündem"

            return j.get("ozet", grup[0]['metin']), kat
        except Exception as e:
            print(f"[{self.tenant_id}] AI JSON Parse Hatası: {e}", flush=True)
            return grup[0]['metin'], "Gündem"

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
        print(f"[{self.tenant_id}] Scraper threadi basliyor...", flush=True)
        self.start_browser()
        if not self.driver:
            print(f"[{self.tenant_id}] Driver baslatilamadigi icin thread sonlaniyor.", flush=True)
            return

        while self.running:
            try:
                settings = self.get_settings()
                if not self.oturum_kontrol():
                    current_time = time.time()
                    # 5 dakikada bir uyar, surekli spam atma
                    if current_time - self._last_login_warning_time > 300:
                        print(f"[{self.tenant_id}] Lütfen X oturumu açın (tarayıcı penceresinden giriş yapınız).")
                        self._last_login_warning_time = current_time
                    time.sleep(15)
                    continue
                else:
                    self._last_login_warning_time = 0

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
                self.tweet_buffer = [t for t in self.tweet_buffer if (simdiki_zaman - t.get('timestamp', 0)) < 1200][-500:]

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
                self.next_scan_time = time.time() + bekleme
                # Sleep in chunks to allow interruption
                for _ in range(bekleme):
                    if not self.running: break
                    time.sleep(1)

            except Exception as e:
                print(f"[{self.tenant_id}] Tarayıcı çöktü veya kapandı. Hata: {e}", flush=True)
                print(f"[{self.tenant_id}] Tarayıcı yeniden başlatılıyor (Auto-Recovery)...", flush=True)
                # Kırık driver'i temizle
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None

                # Biraz dinlenip yeniden başlat
                time.sleep(5)
                self.start_browser()
                if not self.driver:
                    print(f"[{self.tenant_id}] Auto-Recovery basarisiz oldu. Driver baslatilamadi.", flush=True)
                    self.running = False

        self.stop()
