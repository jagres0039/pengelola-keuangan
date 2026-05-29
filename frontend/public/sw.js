// Minimal service worker that caches the app shell and serves a fallback
// when the network is unavailable. API requests always go through the
// network. Navigation requests use network-first so feature releases
// propagate the next time the user is online — only fall back to the
// cached app shell when offline.

const CACHE = "pengelola-keuangan-v4";
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
  if (url.pathname.startsWith("/api/")) return;
  if (url.origin !== self.location.origin) return;

  // Navigation (HTML page) requests: network-first so deploys propagate.
  // Also treat ".rsc" payloads (Next.js React Server Component) as
  // navigation-equivalent — they pair with HTML pages.
  const isNav = req.mode === "navigate" || url.pathname.endsWith(".rsc");
  if (isNav) {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy).catch(() => undefined));
          return resp;
        })
        .catch(() => caches.match(req).then((c) => c || caches.match("/"))),
    );
    return;
  }

  // Static assets: cache-first (immutable hashed chunks under /_next/static).
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
});
