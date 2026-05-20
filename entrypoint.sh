#!/bin/bash

# Sanal ekran çözünürlüğü ve renk derinliği
export DISPLAY=:99
export RESOLUTION="1280x720x24"

echo "Sanal ekran (Xvfb) başlatılıyor..."
Xvfb $DISPLAY -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &
sleep 2

echo "Pencere yöneticisi (Fluxbox) başlatılıyor..."
fluxbox &
sleep 1

echo "VNC Sunucusu başlatılıyor (Port 5900)..."
x11vnc -display $DISPLAY -forever -usepw -shared -rfbport 5900 &
sleep 2

echo "Python uygulaması başlatılıyor..."
python3 app.py
