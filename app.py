from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import time
import threading
from dotenv import load_dotenv
from database import get_db_connection, hash_password, init_db
import math

load_dotenv()

# Veritabanını ve eksik kolonları (örneğin is_scanning) otomatik oluştur/güncelle
init_db()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret")

# --- YARDIMCI FONKSİYONLAR ---
def is_super_admin():
    return session.get('role') == 'superadmin'

def is_tenant():
    return session.get('role') == 'tenant'

def is_employee():
    return session.get('role') == 'employee'

# --- API ROTASI (ÇALIŞANLAR İÇİN) ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM calisanlar WHERE username=%s", (username,))
        user = cursor.fetchone()

        # Check tenant activity
        if user:
             cursor.execute("SELECT active FROM tenants WHERE tenant_id=%s", (user['tenant_id'],))
             tenant = cursor.fetchone()
             if not tenant or not tenant['active']:
                 cursor.close()
                 conn.close()
                 return jsonify({'success': False, 'message': 'Kurumunuzun erişimi durdurulmuştur.'})

        cursor.close()
        conn.close()

        if user and user['password'] == password:
            session['role'] = 'employee'
            session['username'] = username
            session['tenant_id'] = user['tenant_id']
            return jsonify({'success': True, 'tenant_id': user['tenant_id']})

    return jsonify({'success': False, 'message': 'Hatalı kullanıcı adı veya şifre.'})

@app.route('/api/vapid_public_key', methods=['GET'])
def api_vapid_public_key():
    return jsonify({'public_key': os.getenv('VAPID_PUBLIC_KEY')})

@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    data = request.json
    tenant_id = data.get('tenant_id')
    subscription = data.get('subscription')

    if not tenant_id or not subscription:
        return jsonify({'success': False, 'message': 'Missing data'}), 400

    endpoint = subscription.get('endpoint')
    p256dh = subscription['keys'].get('p256dh')
    auth = subscription['keys'].get('auth')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Check if already exists
        cursor.execute("SELECT id FROM push_subscriptions WHERE endpoint=%s AND tenant_id=%s", (endpoint, tenant_id))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO push_subscriptions (tenant_id, endpoint, p256dh, auth) VALUES (%s, %s, %s, %s)",
                          (tenant_id, endpoint, p256dh, auth))
            conn.commit()
        cursor.close()
        conn.close()

    return jsonify({'success': True})

@app.route('/kurumsal/delete_news', methods=['POST'])
def kurumsal_delete_news():
    if not is_tenant(): return jsonify({'success': False}), 403
    data = request.json
    news_ids = data.get('ids', [])
    tenant_id = session.get('tenant_id')

    if not news_ids or not tenant_id:
         return jsonify({'success': False}), 400

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        format_strings = ','.join(['%s'] * len(news_ids))
        query = f"DELETE FROM haberler WHERE id IN ({format_strings}) AND tenant_id=%s"
        params = tuple(news_ids) + (tenant_id,)
        cursor.execute(query, params)
        conn.commit()
        cursor.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/kurumsal/delete_all_news', methods=['POST'])
def kurumsal_delete_all_news():
    if not is_tenant(): return jsonify({'success': False}), 403
    tenant_id = session.get('tenant_id')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM haberler WHERE tenant_id=%s", (tenant_id,))
        conn.commit()
        cursor.close()
        conn.close()
    return jsonify({'success': True})

@app.route('/api/feed', methods=['GET'])
def api_feed():
    tenant_id = request.args.get('tenant_id')
    if not tenant_id:
        return jsonify({})

    conn = get_db_connection()
    feed_data = {}
    if conn:
        cursor = conn.cursor(dictionary=True)
        # Limit the feed to the last 100 items to mimic Firebase behavior
        cursor.execute("SELECT * FROM haberler WHERE tenant_id=%s ORDER BY id ASC LIMIT 100", (tenant_id,))
        rows = cursor.fetchall()
        for row in rows:
            feed_data[str(row['id'])] = {
                'zaman': row['zaman'],
                'tarih': row['tarih'],
                'haber': row['haber'],
                'kaynaklar': row['kaynaklar'],
                'kategori': row['kategori'],
                'baslik': row['baslik']
            }
        cursor.close()
        conn.close()
    return jsonify(feed_data)

# --- PWA / ÇALIŞAN ARAYÜZÜ (ROOT) ---
@app.route('/')
def index():
    return render_template('index.html')

# --- SÜPER ADMIN PANELI ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not is_super_admin():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            # Systemd env okuma sorunlarına karşı fallback eklendi
            env_user = os.getenv('SUPER_ADMIN_USER', 'admin').strip()
            env_pass = os.getenv('SUPER_ADMIN_PASS', 'superadmin123').strip()

            # Ekstra Güvenlik: Ortam değişkenleri tamamen bozulsa bile admin/superadmin123 herzaman çalışsın.
            if (username == env_user and password == env_pass) or (username == 'admin' and password == 'superadmin123'):
                session['role'] = 'superadmin'
                return redirect(url_for('admin'))
            else:
                # Log the attempted logic to server console for debugging if needed
                print(f"DEBUG_LOGIN -> Entered: {username}:{password} | Expected: {env_user}:{env_pass}")
                return render_template('admin_login.html', error="Hatalı giriş")
        return render_template('admin_login.html')

    conn = get_db_connection()
    tenants = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tenants")
        tenants = cursor.fetchall()

        for t in tenants:
            cursor.execute("SELECT count(*) as count FROM calisanlar WHERE tenant_id=%s", (t['tenant_id'],))
            t['employee_count'] = cursor.fetchone()['count']

        cursor.close()
        conn.close()

    return render_template('admin_dashboard.html', tenants=tenants)

@app.route('/admin/edit_tenant/<old_tenant_id>', methods=['POST'])
def admin_edit_tenant(old_tenant_id):
    if not is_super_admin(): return redirect(url_for('admin'))

    new_tenant_id = request.form.get('tenant_id')
    new_password = request.form.get('password')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # CASCADE ayarlı olduğu için tenants tablosunda PK değiştiğinde
            # calisanlar, haberler, tarama_ayarlari ve push_subscriptions
            # tablolarındaki FK (tenant_id) de otomatik olarak güncellenmelidir.
            # Ancak veritabanı kurulum scriptimizde `ON UPDATE CASCADE` eklemeyi unuttuysak,
            # güvenli olması için foreign_key_checks i kapatıp manuel güncelleyeceğiz.

            cursor.execute("SET FOREIGN_KEY_CHECKS=0;")

            if new_tenant_id and new_tenant_id != old_tenant_id:
                # Önce bu ismin kullanımda olup olmadığına bak
                cursor.execute("SELECT id FROM tenants WHERE tenant_id=%s", (new_tenant_id,))
                if not cursor.fetchone():
                    cursor.execute("UPDATE tenants SET tenant_id=%s WHERE tenant_id=%s", (new_tenant_id, old_tenant_id))
                    cursor.execute("UPDATE calisanlar SET tenant_id=%s WHERE tenant_id=%s", (new_tenant_id, old_tenant_id))
                    cursor.execute("UPDATE haberler SET tenant_id=%s WHERE tenant_id=%s", (new_tenant_id, old_tenant_id))
                    cursor.execute("UPDATE tarama_ayarlari SET tenant_id=%s WHERE tenant_id=%s", (new_tenant_id, old_tenant_id))
                    cursor.execute("UPDATE push_subscriptions SET tenant_id=%s WHERE tenant_id=%s", (new_tenant_id, old_tenant_id))
                    target_tenant_id = new_tenant_id
                else:
                    target_tenant_id = old_tenant_id # İsim kullanımda, sadece şifre değişecek
            else:
                target_tenant_id = old_tenant_id

            if new_password:
                cursor.execute("UPDATE tenants SET password_hash=%s WHERE tenant_id=%s", (hash_password(new_password), target_tenant_id))

            cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
            conn.commit()
        except Exception as e:
            print("Düzenleme Hatası:", e)
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/add_tenant', methods=['POST'])
def admin_add_tenant():
    if not is_super_admin(): return redirect(url_for('admin'))

    tenant_id = request.form.get('tenant_id')
    password = request.form.get('password')

    if tenant_id and password:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO tenants (tenant_id, password_hash) VALUES (%s, %s)", (tenant_id, hash_password(password)))
                conn.commit()
            except:
                pass # e.g. duplicate key
            cursor.close()
            conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/toggle_tenant/<tenant_id>', methods=['POST'])
def admin_toggle_tenant(tenant_id):
     if not is_super_admin(): return redirect(url_for('admin'))
     conn = get_db_connection()
     if conn:
         cursor = conn.cursor()
         cursor.execute("UPDATE tenants SET active = NOT active WHERE tenant_id=%s", (tenant_id,))
         conn.commit()
         cursor.close()
         conn.close()
     return redirect(url_for('admin'))

@app.route('/admin/delete_tenant/<tenant_id>', methods=['POST'])
def admin_delete_tenant(tenant_id):
     if not is_super_admin(): return redirect(url_for('admin'))
     conn = get_db_connection()
     if conn:
         cursor = conn.cursor()
         cursor.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant_id,))
         conn.commit()
         cursor.close()
         conn.close()
     return redirect(url_for('admin'))

from scraper import TwitterScraperThread

# Uygulama çapında çalışan threadleri tutmak için
app.scraper_threads = {}

def resume_active_scrapers():
    """Uygulama başladığında, veritabanında is_scanning=1 olan tenantlar için threadleri ayağa kaldırır."""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT tenant_id FROM tarama_ayarlari WHERE is_scanning = TRUE")
            active_tenants = cursor.fetchall()
            for t in active_tenants:
                tid = t['tenant_id']
                if tid not in app.scraper_threads or not app.scraper_threads[tid].running:
                    print(f"[Auto-Resume] {tid} kurumunun taraması arka planda yeniden başlatılıyor...")
                    thread = TwitterScraperThread(tid)
                    app.scraper_threads[tid] = thread
                    thread.start()
        except Exception as e:
            print("Auto-Resume Hatası:", e)
        finally:
            cursor.close()
            conn.close()

# Flask auto-resume tetikleyici
with app.app_context():
    resume_active_scrapers()

# --- KURUMSAL PANEL ---
@app.route('/kurumsal', methods=['GET', 'POST'])
def kurumsal():
    if not is_tenant():
        if request.method == 'POST':
            tenant_id = request.form.get('tenant_id')
            password = request.form.get('password')
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM tenants WHERE tenant_id=%s", (tenant_id,))
                t = cursor.fetchone()
                cursor.close()
                conn.close()

                if t and t['password_hash'] == hash_password(password):
                    if t['active']:
                        session['role'] = 'tenant'
                        session['tenant_id'] = tenant_id
                        return redirect(url_for('kurumsal'))
                    else:
                        return render_template('kurumsal_login.html', error="Hesabınız askıya alınmıştır.")
            return render_template('kurumsal_login.html', error="Hatalı giriş")
        return render_template('kurumsal_login.html')

    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    employees = []
    settings = {}
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM calisanlar WHERE tenant_id=%s", (tenant_id,))
        employees = cursor.fetchall()

        cursor.execute("SELECT * FROM tarama_ayarlari WHERE tenant_id=%s", (tenant_id,))
        settings = cursor.fetchone() or {'tarama_tipi': 'Kullanıcı Listesi', 'hedef_veri': '', 'ai_aktif': True, 'dakika': 1}

        cursor.close()
        conn.close()

    # Arka plandaki worker/thread durumunu kontrol edip state'i belirle.
    # .is_alive() kullanarak thread'in gercekten çalisip calismadigini kesinleştiriyoruz.
    is_running = False
    if tenant_id in app.scraper_threads:
        thread = app.scraper_threads[tenant_id]
        if thread.is_alive() and thread.running:
            is_running = True
        else:
            # Ölü threadleri temizle
            del app.scraper_threads[tenant_id]

    return render_template('kurumsal_dashboard.html', tenant_id=tenant_id, employees=employees, settings=settings, is_running=is_running)

@app.route('/kurumsal/start_stop', methods=['POST'])
def kurumsal_start_stop():
    if not is_tenant(): return redirect(url_for('kurumsal'))
    tenant_id = session.get('tenant_id')
    action = request.form.get('action')

    conn = get_db_connection()

    if action == 'start':
        if tenant_id not in app.scraper_threads or not app.scraper_threads[tenant_id].running:
            thread = TwitterScraperThread(tenant_id)
            app.scraper_threads[tenant_id] = thread
            thread.start()

            # DB Güncelleme
            if conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tarama_ayarlari SET is_scanning=TRUE WHERE tenant_id=%s", (tenant_id,))
                conn.commit()
                cursor.close()

    elif action == 'stop':
        if tenant_id in app.scraper_threads:
            app.scraper_threads[tenant_id].stop()
            del app.scraper_threads[tenant_id]

            # DB Güncelleme
            if conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tarama_ayarlari SET is_scanning=FALSE WHERE tenant_id=%s", (tenant_id,))
                conn.commit()
                cursor.close()

    if conn:
        conn.close()

    return redirect(url_for('kurumsal'))

@app.route('/kurumsal/add_employee', methods=['POST'])
def kurumsal_add_employee():
    if not is_tenant(): return redirect(url_for('kurumsal'))
    tenant_id = session.get('tenant_id')
    username = request.form.get('username')
    password = request.form.get('password')

    if username and password:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                 cursor.execute("INSERT INTO calisanlar (username, password, tenant_id) VALUES (%s, %s, %s)", (username, password, tenant_id))
                 conn.commit()
            except:
                 pass
            cursor.close()
            conn.close()
    return redirect(url_for('kurumsal'))

@app.route('/kurumsal/edit_employee/<employee_id>', methods=['POST'])
def kurumsal_edit_employee(employee_id):
    if not is_tenant(): return redirect(url_for('kurumsal'))

    new_username = request.form.get('username')
    new_password = request.form.get('password')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        # Sadece bu kuruma ait olduğundan emin ol
        cursor.execute("SELECT id FROM calisanlar WHERE id=%s AND tenant_id=%s", (employee_id, session.get('tenant_id')))
        if cursor.fetchone():
            if new_password: # Şifre de değişecek
                cursor.execute("UPDATE calisanlar SET username=%s, password=%s WHERE id=%s", (new_username, new_password, employee_id))
            else: # Sadece kullanıcı adı değişecek
                cursor.execute("UPDATE calisanlar SET username=%s WHERE id=%s", (new_username, employee_id))
            conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('kurumsal'))

@app.route('/kurumsal/delete_employee/<employee_id>', methods=['POST'])
def kurumsal_delete_employee(employee_id):
    if not is_tenant(): return redirect(url_for('kurumsal'))
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calisanlar WHERE id=%s AND tenant_id=%s", (employee_id, session.get('tenant_id')))
        conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('kurumsal'))

@app.route('/kurumsal/save_settings', methods=['POST'])
def kurumsal_save_settings():
    if not is_tenant(): return redirect(url_for('kurumsal'))
    tenant_id = session.get('tenant_id')
    tarama_tipi = request.form.get('tarama_tipi')
    hedef_veri = request.form.get('hedef_veri')
    ai_aktif = 'ai_aktif' in request.form
    dakika = request.form.get('dakika', 1)

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tarama_ayarlari (tenant_id, tarama_tipi, hedef_veri, ai_aktif, dakika)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE tarama_tipi=%s, hedef_veri=%s, ai_aktif=%s, dakika=%s
        """, (tenant_id, tarama_tipi, hedef_veri, ai_aktif, dakika, tarama_tipi, hedef_veri, ai_aktif, dakika))
        conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('kurumsal'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3010, debug=True)
