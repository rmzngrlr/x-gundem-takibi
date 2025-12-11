# 🧠 X Gündem Takibi (Twitter AI Analyst)

**X Gündem Takibi**, belirlediğiniz Twitter (X) hesaplarını anlık olarak izleyen, ortak konuşulan konuları tespit eden ve **Google FLAN-T5 Large** yapay zeka modelini kullanarak bu konuları objektif bir haber diliyle özetleyen gelişmiş bir analiz aracıdır.


## 🚀 Özellikler

* **🕵️ Gizli Tarama:** `undetected_chromedriver` kullanarak Twitter'ın bot korumasına takılmadan veri çeker.
* **🤖 Yapay Zeka Analizi:** Tweetleri İngilizceye çevirir, `flan-t5-large` modeli ile analiz eder ve Türkçe özet çıkarır.
* **⚡ Akıllı Hız Optimizasyonu:** `twitter.com/home` beklemesini atlayarak doğrudan hedef hesaplara odaklanır.
* **📢 Telegram Entegrasyonu:** Tespit edilen önemli gündemleri ve özetleri anında telefonunuza bildirir.
* **🛡️ Tekrar ve Halüsinasyon Koruması:** Yapay zekanın aynı şeyleri tekrarlamasını ve uydurma bilgiler eklemesini engelleyen özel prompt mühendisliği içerir.
* **📂 Geçmiş Arşivi:** Geçmiş analizleri saat ve başlık bazında saklar.
* **🎨 Modern Arayüz:** Streamlit tabanlı, kullanıcı dostu ve temiz bir kontrol paneli.

## 🛠️ Kurulum

Projeyi bilgisayarınıza klonlayın ve gerekli kütüphaneleri yükleyin.

1.  **Repoyu Klonlayın (İndirin):**
    ```bash
    git clone [https://github.com/kullaniciadi/x-gundem-takibi.git](https://github.com/kullaniciadi/x-gundem-takibi.git)
    cd x-gundem-takibi
    ```

2.  **Gereksinimleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Chrome Tarayıcı:**
    Sistemin çalışması için bilgisayarınızda Google Chrome tarayıcısının yüklü olması gerekmektedir.

## ▶️ Kullanım

Uygulamayı başlatmanın tek yolu vardır:

### Yöntem: Tek Tıkla Başlatma (Windows) 🖱️

Proje klasöründe bulunan **`baslat.bat`** dosyasına çift tıklayarak uygulamayı otomatik olarak başlatabilirsiniz.