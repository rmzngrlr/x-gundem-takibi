# 📡 X Gündem Raporu (Kurumsal İstihbarat Paneli)

**X Gündem Raporu**, kurumlar için geliştirilmiş, Twitter (X) üzerindeki verileri anlık olarak izleyen, yapay zeka ile özetleyen ve kurumsal hiyerarşiye uygun olarak raporlayan gelişmiş bir istihbarat sistemidir.

## 🚀 Öne Çıkan Özellikler

* **🤖 Hibrit Yapay Zeka:** 
    * **Groq (Llama-3):** Haberleri tarafsız, profesyonel bir dille özetler ve kategorize eder (Politika, Ekonomi, Gündem, Spor).
    * **Scikit-Learn (TF-IDF & Cosine Similarity):** Tweetleri anlamsal olarak gruplar ve tekrarları önler.
    * **Stemmed Jaccard & Fuzzy Matching:** Kelime oyunlarıyla (örn. "DAEŞ" vs "DEAŞ") yapılan mükerrer haberleri yakalar ve engeller.

* **🔐 3 Katmanlı Kurumsal Kimlik Doğrulama:**
    1.  **Süper Yönetici (Admin):** Kurumları (Tenant) oluşturur, şifrelerini yönetir ve aktiflik durumlarını kontrol eder.
    2.  **Kurum Yöneticisi (Tenant):** Kuruma özel panelden sistemi yönetir, personellerini (çalışanlarını) ekler/siler.
    3.  **Çalışan (Personel):** Web arayüzü (PWA) üzerinden kendine verilen kullanıcı adı/şifre ile giriş yapar ve sadece kendi kurumunun akışını izler.

* **📱 Çoklu Platform & PWA (Progressive Web App):**
    * **Frontend:** Firebase üzerinde çalışan, mobil uyumlu (iOS/Android), uygulama benzeri deneyim sunan web arayüzü.
    * **Backend:** Python (Streamlit) tabanlı veri işleme merkezi.
    * **Bildirimler:** 
        * **Android:** Yüksek öncelikli (`high priority`) bildirimlerle uyuyan cihazları uyandırır.
        * **iOS:** Çift bildirim sorununu çözen özel `prevent_duplicate` mekanizması ile sorunsuz çalışır.

* **🛡️ Güvenlik & Gizlilik:**
    * **Veri İzolasyonu:** Her kurumun verisi Firebase üzerinde ayrıştırılmış düğümlerde (`tenants/{tid}`) saklanır.
    * **Headless Tarayıcı:** `undetected_chromedriver` ile X bot korumalarına takılmadan arka planda veri toplar.

## 🛠️ Kurulum ve Çalıştırma

Bu proje **Windows** ortamında çalışmak üzere optimize edilmiştir.

### 1. Gereksinimler
* Python 3.10 veya 3.11
* Google Chrome Tarayıcısı

### 2. Bağımlılıkları Yükleyin
Proje dizininde terminali açın:
```bash
pip install -r requirements.txt
```

### 3. Sistemi Başlatın
**`AnaMenu.bat`** dosyasına çift tıklayın. Karşınıza gelen menüden:
1.  **Yönetici Paneli:** Kurum eklemek/yönetmek için (`admin_panel.py`).
2.  **Kullanıcı Paneli:** Haber takibini başlatmak ve çalışanları yönetmek için (`twitter_final.py`).

## 📂 Proje Yapısı

* **`twitter_final.py` (Backend):** Veri toplama, AI analizi, Firebase senkronizasyonu ve çalışan yönetimi.
* **`public/index.html` (Frontend):** Son kullanıcılar için PWA arayüzü. Haber akışı ve giriş ekranı.
* **`admin_panel.py`:** Süper yönetici için kurum yönetim arayüzü.
* **`firebase-messaging-sw.js`:** Arka plan bildirim servisi (Service Worker).
* **`GirisEkrani.py`:** Ana menü arayüzü (Tkinter).

## 🌍 Web Arayüzü (PWA)

Çalışanlar, oluşturulan web uygulaması URL'sine (Firebase Hosting) giderek:
1.  Kurum yöneticisi tarafından verilen **Kullanıcı Adı** ve **Şifre** ile giriş yapar.
2.  iOS veya Android cihazlarına "Ana Ekrana Ekle" diyerek uygulama gibi kullanabilir.
3.  Anlık bildirimleri alabilir.

---
*Geliştirildi: [Tarih]*
