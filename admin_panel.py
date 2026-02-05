import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
from datetime import datetime
import hashlib

# ==========================================
# ⚙️ AYARLAR
# ==========================================
FIREBASE_DB_URL = "https://x-gundem-raporu-default-rtdb.europe-west1.firebasedatabase.app"

st.set_page_config(page_title="Süper Admin Paneli", page_icon="👮", layout="wide")

# Firebase Init
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DB_URL
        })
    except Exception as e:
        st.error(f"Firebase Bağlantı Hatası: {e}")
        st.stop()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

st.title("👮 Süper Admin - Kurum Yönetimi")
st.markdown("""
    <style>
    /* Hide Streamlit header anchors */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)
st.markdown("---")

# --- BEKLEYEN ŞİFRE TALEPLERİ ---
try:
    req_ref = db.reference('password_requests')
    requests_data = req_ref.get()
except: requests_data = None

if requests_data:
    st.info(f"🔔 {len(requests_data)} adet bekleyen şifre değiştirme talebi var.")
    with st.expander("Gelen Talepleri İncele", expanded=True):
        for tid, r_data in requests_data.items():
            col_r1, col_r2 = st.columns([3, 1])
            with col_r1:
                st.write(f"**{tid}** - {r_data.get('timestamp')}")
            with col_r2:
                c_yes, c_no = st.columns(2)
                with c_yes:
                    if st.button("✔️", key=f"app_{tid}"):
                        db.reference(f'tenants_auth/{tid}').update({'password_hash': r_data['new_password_hash']})
                        db.reference(f'password_requests/{tid}').delete()
                        st.success("Onaylandı!")
                        st.rerun()
                with c_no:
                    if st.button("❌", key=f"rej_{tid}"):
                        db.reference(f'password_requests/{tid}').delete()
                        st.warning("Reddedildi.")
                        st.rerun()
    st.divider()

# --- YENİ KURUM EKLEME ---
with st.expander("➕ Yeni Kurum Ekle", expanded=True):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_tenant_id = st.text_input("Kurum Adı (Kullanıcı Adı)", help="Boşluksuz ve benzersiz bir ID kullanın.")
    with col2:
        new_password = st.text_input("Kurum Şifresi", type="password")
    with col3:
        st.write("") # Spacer
        st.write("") # Spacer
        if st.button("Kurumu Kaydet", use_container_width=True):
            if new_tenant_id and new_password:
                ref = db.reference(f'tenants_auth/{new_tenant_id}')
                if ref.get():
                    st.error("Bu Kurum Adı zaten kullanımda!")
                else:
                    ref.set({
                        "password_hash": hash_password(new_password),
                        "active": True,
                        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    st.success(f"✅ {new_tenant_id} başarıyla oluşturuldu!")
                    st.rerun()
            else:
                st.warning("Lütfen Kurum Adı ve Şifre giriniz.")

st.divider()

# --- KURUMLARI LİSTELE ---
st.subheader("📋 Kayıtlı Kurumlar")

try:
    tenants_ref = db.reference('tenants_auth')
    tenants_data = tenants_ref.get()
    
    # Tüm çalışanları bir kerede çek (Index hatasını önlemek için)
    all_calisanlar = db.reference('calisanlar').get() or {}
except Exception as e:
    st.error(f"Veri çekilemedi: {e}")
    tenants_data = None
    all_calisanlar = {}

if tenants_data:
    # Veriyi tablo formatına çevir
    for tenant_id, data in tenants_data.items():
        is_active = data.get('active', True)
        created_at = data.get('created_at', '-')
        
        with st.container():
            c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
            
            with c1:
                st.write(f"🏢 **{tenant_id}**")
            
            with c2:
                st.caption(f"Kayıt: {created_at}")
            
            with c3:
                if is_active:
                    st.success("AKTİF")
                else:
                    st.error("PASİF")
            
            with c4:
                # Durum Değiştir
                btn_label = "Pasife Al" if is_active else "Aktife Al"
                if st.button(btn_label, key=f"toggle_{tenant_id}"):
                    tenants_ref.child(tenant_id).update({'active': not is_active})
                    st.rerun()
                
                # Şifre Değiştir (Admin Manuel)
                with st.popover("Şifre Değiştir"):
                    admin_new_pass = st.text_input("Yeni Şifre", type="password", key=f"adm_pass_{tenant_id}")
                    if st.button("Kaydet", key=f"adm_save_{tenant_id}"):
                        if admin_new_pass:
                            tenants_ref.child(tenant_id).update({'password_hash': hash_password(admin_new_pass)})
                            st.success("Şifre güncellendi.")
                        else:
                            st.warning("Şifre giriniz.")

                # Sil
                if st.button("Sil 🗑️", key=f"del_{tenant_id}"):
                    tenants_ref.child(tenant_id).delete()
                    st.rerun()
            
            # --- ÇALIŞAN YÖNETİMİ (EXPANDER) ---
            with st.expander(f"👥 {tenant_id} - Çalışanlarını Yönet"):
                # Bu kuruma ait çalışanları filtrele
                tenant_employees = {k: v for k, v in all_calisanlar.items() if v.get('tenant_id') == tenant_id}
                
                if tenant_employees:
                    for k, v in tenant_employees.items():
                        st.markdown(f"**👤 {k}**")
                        # Düzenleme Formu
                        with st.form(key=f"form_edit_{tenant_id}_{k}"):
                            col_e1, col_e2, col_e3 = st.columns([2, 2, 1])
                            with col_e1:
                                new_u_name = st.text_input("Kullanıcı Adı", value=k)
                            with col_e2:
                                new_u_pass = st.text_input("Yeni Şifre (Değişmeyecekse boş)", type="password")
                            with col_e3:
                                st.write("")
                                st.write("")
                                if st.form_submit_button("Güncelle"):
                                    try:
                                        # Şifre Değişimi
                                        if new_u_name == k:
                                            if new_u_pass:
                                                db.reference(f'calisanlar/{k}').update({'sifre': new_u_pass})
                                                st.success("Şifre güncellendi!")
                                                st.rerun()
                                            else:
                                                st.info("Değişiklik yok.")
                                        # Kullanıcı Adı Değişimi
                                        else:
                                            check_ref = db.reference(f'calisanlar/{new_u_name}')
                                            if check_ref.get():
                                                st.error("Kullanıcı adı kullanımda!")
                                            else:
                                                pass_to_save = new_u_pass if new_u_pass else v.get('sifre')
                                                check_ref.set({
                                                    'sifre': pass_to_save,
                                                    'tenant_id': tenant_id
                                                })
                                                db.reference(f'calisanlar/{k}').delete()
                                                st.success("Kullanıcı güncellendi!")
                                                st.rerun()
                                    except Exception as e: st.error(str(e))
                        
                        if st.button("Çalışanı Sil 🗑️", key=f"del_emp_{tenant_id}_{k}"):
                            db.reference(f'calisanlar/{k}').delete()
                            st.rerun()
                        st.divider()
                else:
                    st.info("Bu kuruma kayıtlı çalışan yok.")

            st.markdown("---")
else:
    st.info("Henüz kayıtlı bir kurum yok.")
