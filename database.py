import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import hashlib

load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "secret"),
            database=os.getenv("DB_NAME", "xgundem"),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Error as e:
        print(f"Veritabanı bağlantı hatası: {e}")
        return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    # Database'i oluşturmak için connection string (DB_NAME olmadan)
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "secret")
        )
        cursor = conn.cursor()
        db_name = os.getenv("DB_NAME", "xgundem")

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"Veritabanı '{db_name}' oluşturuldu veya zaten var.")

        cursor.close()
        conn.close()
    except Error as e:
         print(f"Veritabanı oluşturma hatası: {e}")
         return

    # Tabloları oluştur
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()

        # Kurumlar (Tenants) Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tenants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tenant_id VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Çalışanlar Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calisanlar (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                tenant_id VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
            )
        ''')

        # Haberler Tablosu (Firebase Gündem alternatifi)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS haberler (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tenant_id VARCHAR(100) NOT NULL,
                zaman VARCHAR(50),
                tarih VARCHAR(50),
                haber TEXT,
                kaynaklar TEXT,
                kategori VARCHAR(50),
                baslik VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
            )
        ''')

        # Tarama Ayarları Tablosu (Kurumların ayarları)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tarama_ayarlari (
                tenant_id VARCHAR(100) PRIMARY KEY,
                tarama_tipi VARCHAR(50) DEFAULT 'Kullanıcı Listesi',
                hedef_veri TEXT,
                ai_aktif BOOLEAN DEFAULT TRUE,
                dakika INT DEFAULT 1,
                is_scanning BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
            )
        ''')

        # Push Abonelikleri Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tenant_id VARCHAR(100) NOT NULL,
                endpoint TEXT NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        cursor.close()
        conn.close()
        print("Tablolar başarıyla oluşturuldu.")

if __name__ == "__main__":
    init_db()
