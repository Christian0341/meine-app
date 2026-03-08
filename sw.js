const CACHE_NAME = 'meine-app-v1';
const FILES = [
  '/meine-app/',
  '/meine-app/index.html',
  '/meine-app/manifest.json'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(FILES))
  );
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(response => response || fetch(e.request))
  );
});
