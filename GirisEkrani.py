import tkinter as tk
import os

def run_app():
    # Windows 'start' komutu ile streamlit komutunu yeni pencerede çalıştır
    if os.name == 'nt':
        # cmd /k komutu pencerenin açık kalmasını sağlar (hata görürsek diye)
        os.system('start cmd /k "streamlit run twitter_final.py"')
    else:
        print("Bu özellik sadece Windows'ta çalışır.")

def run_admin():
    if os.name == 'nt':
        os.system('start cmd /k "streamlit run admin_panel.py"')
    else:
        print("Bu özellik sadece Windows'ta çalışır.")

# Arayüzü oluştur
root = tk.Tk()
root.title("X Gündem - Ana Menü")
root.geometry("350x200")
root.eval('tk::PlaceWindow . center') # Pencereyi ortala

# Başlık
lbl = tk.Label(root, text="Hoşgeldiniz!\nLütfen giriş yapmak istediğiniz paneli seçin.", font=("Arial", 11), pady=15)
lbl.pack()

# Butonlar
btn_app = tk.Button(root, text="🚀 Kurumsal Panel (Tenant)", command=run_app, font=("Arial", 10, "bold"), bg="#E3F2FD", fg="#0D47A1", width=30, height=2, cursor="hand2")
btn_app.pack(pady=5)

btn_admin = tk.Button(root, text="👮 Süper Admin Paneli", command=run_admin, font=("Arial", 10, "bold"), bg="#FFEBEE", fg="#B71C1C", width=30, height=2, cursor="hand2")
btn_admin.pack(pady=5)

# Alt bilgi
lbl_footer = tk.Label(root, text="X Gündem Raporu v2.0", font=("Arial", 8), fg="gray", pady=10)
lbl_footer.pack(side="bottom")

root.mainloop()
