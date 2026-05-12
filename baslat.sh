#!/bin/bash

# Renkli Çıktı Tanımlamaları
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}         X GÜNDEM RAPORU - BAŞLATICI            ${NC}"
echo -e "${CYAN}================================================${NC}"

# Sanal ortam kontrolü
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Uyarı: 'venv' klasörü bulunamadı! Lütfen önce install.sh ile kurulum yapın.${NC}"
    exit 1
fi

echo -e "${GREEN}Sanal ortam aktif ediliyor...${NC}"
source venv/bin/activate

echo -e "${GREEN}Sistem başlatılıyor... Çıkış yapmak ve sistemi durdurmak için CTRL+C tuşlarına basabilirsiniz.${NC}"
echo -e "----------------------------------------------------------------------"

# Uygulamayı doğrudan başlat ve logları ekrana bas (Python'un buffer yapmasını engellemek için -u kullanılır)
python -u app.py
