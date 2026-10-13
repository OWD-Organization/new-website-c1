(function () {
  var pins = JSON.parse(document.getElementById('rpPins').textContent);
  var cards = Array.prototype.slice.call(document.querySelectorAll('.rp-card'));
  var chips = Array.prototype.slice.call(document.querySelectorAll('.rp-chip'));
  var citySel = document.getElementById('rpCity');
  var count = document.getElementById('rpCount');
  var state = { cat: 'all', city: 'all' }, map = null, markers = {};

  function apply() {
    var n = 0;
    cards.forEach(function (c) {
      var ok = (state.cat === 'all' || c.dataset.cat === state.cat) && (state.city === 'all' || c.dataset.city === state.city);
      c.hidden = !ok; if (ok) n++;
    });
    count.textContent = 'Showing ' + n + (n === 1 ? ' project' : ' projects');
    if (map) {
      var vis = [];
      pins.forEach(function (p) {
        var ok = (state.cat === 'all' || p.cat === state.cat) && (state.city === 'all' || p.city === state.city);
        var m = markers[p.id]; if (!m) return;
        if (ok) { m.addTo(map); vis.push([p.lat, p.lng]); } else { map.removeLayer(m); }
      });
      if (vis.length) map.fitBounds(vis, { padding: [40, 40], maxZoom: 12 });
    }
  }
  chips.forEach(function (b) {
    b.addEventListener('click', function () {
      chips.forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
      b.setAttribute('aria-pressed', 'true'); state.cat = b.dataset.cat; apply();
    });
  });
  citySel.addEventListener('change', function () { state.city = citySel.value; apply(); });

  // photo zoom (native <dialog>: focus trap + Esc handled by the browser)
  var dlg = document.getElementById('rpZoom'), dImg = dlg.querySelector('img'), opener = null;
  document.querySelectorAll('.rp-zoom').forEach(function (b) {
    b.addEventListener('click', function () {
      opener = b; var im = b.querySelector('img'); dImg.src = b.dataset.src; dImg.alt = im.alt;
      if (dlg.showModal) dlg.showModal(); else window.open(b.dataset.src);
    });
  });
  dlg.querySelector('.rp-zclose').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener('close', function () { if (opener) opener.focus(); });

  function initMap() {
    if (!window.L) return;
    map = L.map('rpMap', { scrollWheelZoom: false, keyboard: true }).setView([33.62, -112.0], 10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 13, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    var b = [];
    pins.forEach(function (p) {
      var icon = L.divIcon({ className: '', html: '<div class="rp-pin' + (p.rv ? ' rv' : '') + '"></div>', iconSize: [30, 30], iconAnchor: [15, 30], popupAnchor: [0, -28] });
      var m = L.marker([p.lat, p.lng], { icon: icon, title: p.t + ', ' + p.c + ', ' + p.d, alt: p.t + ' in ' + p.c, keyboard: true })
        .bindPopup('<div class="rp-pop"><strong>' + p.t + '</strong><span>' + p.c + ' &middot; ' + p.d + '</span><a href="#p-' + p.id + '">View project</a></div>')
        .addTo(map);
      markers[p.id] = m; b.push([p.lat, p.lng]);
    });
    if (b.length) map.fitBounds(b, { padding: [40, 40], maxZoom: 12 });
    document.querySelectorAll('.rp-showmap').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var m = markers[btn.dataset.id]; if (!m) return;
        document.getElementById('rpMap').scrollIntoView({ behavior: 'smooth', block: 'center' });
        map.setView(m.getLatLng(), 12); m.openPopup();
      });
    });
  }
  if (document.readyState === 'complete') initMap(); else window.addEventListener('load', initMap);
})();
