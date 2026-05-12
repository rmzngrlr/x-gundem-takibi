#!/bin/bash

# Renkli Çıktı Tanımlamaları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}       X GÜNDEM RAPORU - KURULUM SİHİRBAZI      ${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""
echo -e "${YELLOW}Bu sihirbaz, gerekli paketleri kuracak, VAPID anahtarlarını${NC}"
echo -e "${YELLOW}üretecek ve sisteminizi .env dosyasına kaydedecektir.${NC}"
echo ""

# 1. GEREKSİNİMLERİN YÜKLENMESİ
echo -e "${GREEN}[1/5] Sistem gereksinimleri kontrol ediliyor...${NC}"
sudo apt update
sudo apt install -y python3 python3-pip python3-venv curl jq

# 2. VENV VE BAĞIMLILIKLARIN KURULUMU
echo -e "${GREEN}[2/5] Python sanal ortamı (venv) oluşturuluyor...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo -e "${GREEN}      Python kütüphaneleri kuruluyor (Bu biraz sürebilir)...${NC}"
pip install --upgrade pip
pip install setuptools
pip install -r requirements.txt

# 3. İNTERAKTİF BİLGİ ALIMI VE .ENV OLUŞTURMA
echo ""
echo -e "${GREEN}[3/5] Veritabanı ve Sistem Bilgileri Yapılandırması${NC}"
echo -e "${YELLOW}(Docker MySQL bilgilerinizi giriniz. Boş bırakırsanız parantez içindeki varsayılan değerler kullanılır.)${NC}"

read -p "MySQL Host Adresi (127.0.0.1): " db_host
db_host=${db_host:-127.0.0.1}

read -p "MySQL Portu (3306): " db_port
db_port=${db_port:-3306}

read -p "MySQL Kullanıcı Adı (root): " db_user
db_user=${db_user:-root}

read -s -p "MySQL Şifresi: " db_password
echo ""

read -p "Oluşturulacak Veritabanı Adı (xgundem): " db_name
db_name=${db_name:-xgundem}

echo ""
read -p "Süper Admin Kullanıcı Adı (admin): " admin_user
admin_user=${admin_user:-admin}

read -s -p "Süper Admin Şifresi (superadmin123): " admin_pass
echo ""
admin_pass=${admin_pass:-superadmin123}

echo ""
read -p "Groq API Anahtarınız (Yapay Zeka için): " groq_key
echo ""
read -p "Bildirimler (VAPID) İçin Şirket Mailiniz (admin@example.com): " vapid_mail
vapid_mail=${vapid_mail:-admin@example.com}

# VAPID Anahtarlarını Üret
echo -e "${GREEN}      Web Push (VAPID) anahtarları otomatik üretiliyor...${NC}"
vapid --gen > /dev/null 2>&1
vapid_public=$(vapid --applicationServerKey | awk -F'=' '{print $2}' | xargs)

flask_secret=$(head -c 24 /dev/urandom | base64 | tr -d '+/' | cut -c 1-32)

# .env Dosyasını Yaz
cat <<EOF > .env
# MySQL Database
DB_HOST=$db_host
DB_PORT=$db_port
DB_USER=$db_user
DB_PASSWORD=$db_password
DB_NAME=$db_name

# Groq API Key
GROQ_API_KEY=$groq_key

# Flask App Secret
FLASK_SECRET_KEY=$flask_secret

# Süper Admin Bilgileri
SUPER_ADMIN_USER=$admin_user
SUPER_ADMIN_PASS=$admin_pass

# VAPID Keys
VAPID_PUBLIC_KEY=$vapid_public
VAPID_PRIVATE_KEY=private_key.pem
VAPID_CLAIMS_EMAIL=mailto:$vapid_mail
EOF

echo -e "${CYAN}.env dosyası başarıyla oluşturuldu!${NC}"

# 4. VERİTABANI İNŞASI
echo ""
echo -e "${GREEN}[4/5] MySQL Tabloları oluşturuluyor...${NC}"
python database.py
if [ $? -eq 0 ]; then
    echo -e "${CYAN}Veritabanı işlemleri başarılı.${NC}"
else
    echo -e "${RED}Veritabanı bağlantısında veya tablo oluşturmada hata oluştu! Lütfen MySQL bilgilerinizin doğruluğunu kontrol edin.${NC}"
    exit 1
fi

# 5. SERVİS VE NGINX YAPILANDIRMASI (İSTEĞE BAĞLI)
echo ""
echo -e "${GREEN}[5/5] Son Adımlar ve SSL / Yayınlama Ayarları${NC}"
read -p "Nginx ve Let's Encrypt (SSL) kurup sistemi dışa açmak ister misiniz? (E/H) " ssl_choice

if [[ "$ssl_choice" == "E" || "$ssl_choice" == "e" ]]; then
    read -p "Lütfen bağlanacak alan adınızı girin (Örn: haberler.sirket.com): " domain_name

    sudo apt install -y nginx certbot python3-certbot-nginx

    # Nginx Yapılandırması
    cat <<EOF | sudo tee /etc/nginx/sites-available/xgundem
server {
    server_name $domain_name;

    location / {
        proxy_pass http://127.0.0.1:3010;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    sudo ln -s /etc/nginx/sites-available/xgundem /etc/nginx/sites-enabled/ 2>/dev/null
    sudo nginx -t
    if [ $? -eq 0 ]; then
        sudo systemctl restart nginx
        echo -e "${CYAN}Nginx ayarlandı. Şimdi SSL Sertifikası alınıyor...${NC}"
        sudo certbot --nginx -d $domain_name
    else
        echo -e "${RED}Nginx ayarlarında hata var, atlanıyor.${NC}"
    fi
fi

# SYSTEMD SERVİSİ (Arka planda çalışması için)
read -p "Uygulamanın sunucu yeniden başladığında otomatik çalışmasını (Systemd Servisi) ister misiniz? (E/H) " sys_choice
if [[ "$sys_choice" == "E" || "$sys_choice" == "e" ]]; then
    APP_DIR=$(pwd)
    USER_NAME=$USER

    cat <<EOF | sudo tee /etc/systemd/system/xgundem.service
[Unit]
Description=X Gundem Raporu Flask App
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/$USER_NAME/.Xauthority"
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable xgundem.service
    sudo systemctl start xgundem.service
    echo -e "${CYAN}Systemd servisi kuruldu ve başlatıldı! 'sudo systemctl status xgundem' ile durumunu görebilirsiniz.${NC}"
else
    echo -e "${YELLOW}Uygulamayı başlatmak için terminalde: source venv/bin/activate && python app.py komutunu kullanın.${NC}"
fi

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}          KURULUM BAŞARIYLA TAMAMLANDI!         ${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "Arayüze girmek için (SSL kurduysanız): https://$domain_name"
echo -e "Süper Admin Paneli: /admin"
echo -e "Kurumsal Panel: /kurumsal"
