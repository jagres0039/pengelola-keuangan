// Minimal service worker that caches the app shell and serves a fallback
// when the network is unavailable. API requests always go through the network.

const CACHE = "pengelola-keuangan-v1";
const APP_SHELL = ["/", "/login", "/register", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(APP_SHELL).catch(() => undefined))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // API requests: always network (no cache)
  if (url.pathname.startsWith("/api/")) return;
  // Same-origin static assets: cache-first
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req)
          .then((resp) => {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy).catch(() => undefined));
            return resp;
          })
          .catch(() => caches.match("/"));
      }),
    );
  }
});
