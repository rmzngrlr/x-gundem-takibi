import firebase_admin
from firebase_admin import credentials, db
import os

# Firebase yapılandırması
FIREBASE_DB_URL = "https://x-gundem-raporu-default-rtdb.europe-west1.firebasedatabase.app"

def reset_database():
    try:
        # Service Account Key kontrolü
        if not os.path.exists("serviceAccountKey.json"):
            print("⚠️ serviceAccountKey.json bulunamadı! Veritabanı sıfırlanamadı.")
            return

        # Firebase uygulamasını başlat (eğer zaten başlamadıysa)
        if not firebase_admin._apps:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DB_URL
            })

        # 'gundem' düğümünü sil
        ref = db.reference('gundem')
        ref.delete()
        print("✅ Veritabanı (Gündem) başarıyla sıfırlandı.")

    except Exception as e:
        print(f"❌ Veritabanı sıfırlama hatası: {e}")

if __name__ == "__main__":
    reset_database()
