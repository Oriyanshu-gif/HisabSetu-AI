/* HisabSetu AI service worker.
 *
 * Rules that matter for a money app:
 *  - never cache /api/* — the ledger must always come from the server;
 *  - the app shell is cached so the install opens instantly and survives a
 *    flaky connection;
 *  - bump CACHE_VERSION whenever the shell changes, otherwise phones keep the
 *    old CSS/JS.
 */

const CACHE_VERSION = "hisabsetu-v3";
const SHELL = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/favicon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then((cache) => cache.addAll(SHELL).catch(() => undefined))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Money data: network only. A stale balance is worse than an error.
  if (url.pathname.startsWith("/api/")) return;

  // The worker and the manifest must always be fetched fresh, or updates stall.
  if (url.pathname === "/sw.js" || url.pathname === "/manifest.webmanifest") return;

  // Navigations: try the network, fall back to the cached shell.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put("/", copy)).catch(() => undefined);
          return response;
        })
        .catch(() =>
          caches.match("/").then((cached) => cached || new Response("Offline", { status: 503 }))
        )
    );
    return;
  }

  // Static assets: cache first, refresh in the background.
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy)).catch(() => undefined);
          }
          return response;
        })
        .catch((error) => cached || Promise.reject(error));
      return cached || network;
    })
  );
});
