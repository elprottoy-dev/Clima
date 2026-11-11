const CACHE='clima-shell-v17-dated-updates';
const ASSETS=['/','/style.css','/app.js','/cloud-transport.js','/clinical.js','/upgrade.js','/draft-vault.js','/offline.js','/labels.js','/retention.js','/admin-crud.js','/seasonal.js','/registration.js','/locations.json','/data-notices.js'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.origin!==location.origin||!ASSETS.includes(u.pathname))return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))))});
