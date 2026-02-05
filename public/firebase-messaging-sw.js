importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');

const firebaseConfig = {
    apiKey: "AIzaSyAgIWcLB_yOas3gQ8g5GrJJcala5SGovEU",
    authDomain: "x-gundem-raporu.firebaseapp.com",
    projectId: "x-gundem-raporu",
    storageBucket: "x-gundem-raporu.firebasestorage.app",
    messagingSenderId: "904189656566",
    appId: "1:904189656566:web:a2ada82d829c2a775a5bd7",
    measurementId: "G-EPBRMV0RC6"
};

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Arka plan mesajlarını dinle
messaging.onBackgroundMessage((payload) => {
    console.log('[firebase-messaging-sw.js] Arka plan bildirimi:', payload);

    // iOS KONTROLÜ (Çift Bildirimi Engelleme - Kesin Çözüm)
    // Eğer mesajda "prevent_duplicate" bayrağı varsa, Service Worker bunu göstermez.
    // Çünkü bu mesajın içinde zaten sistem tarafından gösterilecek bir 'notification' payload'ı vardır.
    if (payload.data && payload.data.prevent_duplicate === 'true') {
        console.log("Çift bildirim engellendi (iOS Flag Detected).");
        return; 
    }
    
    // Payload içinden veri al (Data Message)
    // Yeni değişken isimleri: haber_baslik ve haber_ozet (Eski sürümler için title/body kontrolü de eklendi)
    // Optional chaining (?.) yerine klasik kontrol kullanıldı (Eski Android WebView uyumluluğu için)
    const d = payload.data || {};
    const notificationTitle = d.haber_baslik || d.title || "X Gündem Raporu";
    const notificationOptions = {
        body: d.haber_ozet || d.body || "Yeni bir gündem maddesi var.",
        icon: '/ikon.png',
        badge: '/ikon.png',
        tag: 'gundem-bildirim',
        renotify: true,
        data: {
            url: d.url || self.location.origin,
            ...d 
        }
    };

    return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Bildirime tıklanma olayı
self.addEventListener('notificationclick', function(event) {
    console.log('[firebase-messaging-sw.js] Bildirime tıklandı.');
    event.notification.close();

    const targetUrl = event.notification.data.url || self.location.origin;

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            // Eğer uygulama zaten açıksa ona odaklan
            for (var i = 0; i < clientList.length; i++) {
                var client = clientList[i];
                if (client.url === targetUrl && 'focus' in client) {
                    return client.focus();
                }
            }
            // Değilse yeni pencere aç
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
