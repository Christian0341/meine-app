const CACHE_NAME = 'meine-app-v6';
const STATIC_FILES = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon.png'
];
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_FILES))
  );
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  // Alle JSON-Daten immer frisch vom Netzwerk
  if (e.request.url.includes('.json')) {
    e.respondWith(fetch(e.request));
    return;
  }
  // Alles andere: Netzwerk zuerst, Cache als Fallback
  e.respondWith(
    fetch(e.request)
      .then(res => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
