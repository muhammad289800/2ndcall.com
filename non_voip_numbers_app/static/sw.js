const CACHE_NAME = "2ndcall-v1";
const PRECACHE = [
  "/",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

// Install — cache shell assets
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Notification click — open the app
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow('/app'));
});

// Fetch — network-first for API, cache-first for static assets
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Never cache API calls, webhooks, or auth endpoints
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/webhooks/") ||
    e.request.method !== "GET"
  ) {
    return;
  }

  // Static assets & app shell: cache-first, fallback to network
  e.respondWith(
    caches.match(e.request).then((cached) => {
      const networkFetch = fetch(e.request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
          }
          return response;
        })
        .catch(() => cached);

      return cached || networkFetch;
    })
  );
});
