self.addEventListener('push', function(event) {
    if (event.data) {
        try {
            const data = event.data.json();
            const options = {
                body: data.body,
                icon: '/static/ikon.png',
                badge: '/static/ikon.png',
                data: {
                    url: data.url || '/'
                }
            };
            event.waitUntil(
                self.registration.showNotification(data.title || 'X Gündem Raporu', options)
            );
        } catch (e) {
            console.error('Push event data was not valid JSON', e);
        }
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    if (event.notification.data && event.notification.data.url) {
        event.waitUntil(
            clients.matchAll({ type: 'window' }).then(windowClients => {
                for (var i = 0; i < windowClients.length; i++) {
                    var client = windowClients[i];
                    if (client.url.indexOf(event.notification.data.url) !== -1 && 'focus' in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow(event.notification.data.url);
                }
            })
        );
    }
});
