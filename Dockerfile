FROM ubuntu:22.04

# Zaman dilimi ve interaktif olmayan kurulum için
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Istanbul

# Temel paketlerin ve Chrome'un kurulması
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    gnupg \
    xvfb \
    x11vnc \
    fluxbox \
    dbus-x11 \
    libnss3 \
    libgconf-2-4 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Google Chrome'u kur
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# VNC için şifre ayarlama (Opsiyonel güvenlik için)
RUN mkdir -p ~/.vnc && x11vnc -storepasswd "secret" ~/.vnc/passwd

WORKDIR /app

# Proje gereksinimlerini kopyala ve yükle
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Entrypoint scriptine yetki ver
RUN chmod +x /app/entrypoint.sh

# VNC (5900) ve Flask (3010) portlarını aç (Host network kullanacağımız için docker-compose ezecek ama dokümantasyon amaçlı)
EXPOSE 5900 3010

# Başlangıç komutu
CMD ["/app/entrypoint.sh"]
