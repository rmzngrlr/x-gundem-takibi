# 🧠 X Gündem Takibi (AI Agenda Analyst)

**X Gündem Takibi**, belirlediğiniz Twitter (X) hesaplarını veya **Twitter Listelerini** anlık olarak izleyen, paylaşımları kelime bazlı değil **anlam bazlı (semantik)** analiz eden ve yapay zeka ile özetleyerek size raporlayan gelişmiş bir istihbarat aracıdır.

> **v2.17 Güncellemesi:** Artık "Günaydın" gibi gürültü tweetlerini eliyor ve tek bir kaynağın yoğun paylaşımlarını (Son Dakika) da gündem olarak yakalayabiliyor.

## 🚀 Öne Çıkan Özellikler

* **🧠 Semantik Analiz (Yeni):** `sentence-transformers` (Multilingual) modeli sayesinde tweetleri anlamlarına göre gruplar. Farklı kelimelerle aynı şeyi anlatan tweetleri kaçırmaz.
* **🛡️ Çapraz Doğrulama ve Yoğunluk Kuralı (Yeni):** Sahte gündemleri engeller. Bir konunun "Gündem" sayılması için:
    * Ya en az **2 farklı hesap** bu konudan bahsetmeli,
    * Ya da tek bir hesap aynı konuda **en az 3 tweet** atmalıdır (Son Dakika / Yoğunluk Kuralı).
* **🔗 Liste Desteği (Yeni):** Tek tek kullanıcı adı girmek yerine, bir Twitter Liste URL'si (örn: `x.com/i/lists/...`) vererek yüzlerce hesabı aynı anda takip edebilirsiniz.
* **🧹 Akıllı Gürültü Filtresi:** "Günaydın", "Selam", "Hayırlı Cumalar" gibi haber değeri taşımayan tweetleri otomatik olarak algılar ve analize dahil etmez.
* **🕵️ Tam Gizlilik (Headless):** Tarayıcı tamamen arka planda çalışır, ekranda pencere açmaz. `undetected_chromedriver` ile bot korumalarına takılmaz.
* **🤖 Yapay Zeka Özetleme:** Yakalanan gündemleri **Google FLAN-T5 Large** modeli ile objektif bir haber diliyle özetler.
* **⚡ Otomatik Bakım:** Başlangıçta arka planda asılı kalan "zombi" Chrome süreçlerini otomatik temizler.
* **📢 Telegram Entegrasyonu:** Tespit edilen gündemi ve kaynak tweetleri anında cebinize bildirir.

## 🛠️ Kurulum

⚠️ **Önemli:** Projenin sorunsuz çalışması için **Python 3.10** veya **3.11** sürümü gereklidir. (Python 3.13 şu an bazı AI kütüphanelerini desteklememektedir).

1.  **Repoyu İndirin:**
    Projeyi bilgisayarınıza indirin veya klonlayın.

2.  **Gereksinimleri Yükleyin:**
    Terminali (CMD) proje klasöründe açın ve aşağıdaki komutu çalıştırın:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Başlatın:**
    Proje klasöründeki **`baslat.bat`** dosyasına çift tıklayın.

## ⚙️ Kullanım

Uygulama açıldığında sol menüden ayarlarınızı yapabilirsiniz:

* **Tarama Yöntemi:**
    * *Kullanıcı Listesi:* `elonmusk, nasa, bbc` gibi virgülle ayırarak özel takip listesi oluşturun.
    * *Liste URL:* Takip etmek istediğiniz bir X listesinin linkini yapıştırın.
* **Yapay Zeka ile Özetle:** İsterseniz AI özetini kapatıp sadece kaynak linkleri alabilirsiniz.
* **Tarama Sıklığı:** Kaç dakikada bir kontrol edileceğini belirleyin.

## 📦 Gereksinimler (requirements.txt)

```text
streamlit
undetected-chromedriver
selenium
requests
deep-translator
transformers
torch
sentencepiece
protobuf
sentence-transformers

scikit-learn
