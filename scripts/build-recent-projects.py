#!/usr/bin/env python3
"""Render data/recent-projects.json into recent-projects/index.html (static, crawlable).
Only the block between <!-- RP:START --> and <!-- RP:END --> (and the RP-HEAD block) is replaced;
the shared site header/footer are left untouched.   python3 scripts/build-recent-projects.py
"""
import datetime as dt, html, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "recent-projects" / "index.html"
DATA = json.loads((ROOT / "data" / "recent-projects.json").read_text())
E = lambda s: html.escape(str(s), quote=True)

HEAD = """<!-- RP-HEAD:START -->
  <meta name="robots" content="noindex, nofollow" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
  <style id="rp-css">
    .rp-hero { padding: 190px 0 80px; text-align: center; }
    .rp-hero .section-label { justify-content: center; }
    .rp-hero-btns { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-top: var(--space-lg); }
    .rp-hero-btns a { font-size: 1.0625rem; padding: 16px 30px; min-width: 230px; }
    .rp-hero-btns .material-icons { font-size: 1.25rem; }
    .rp-stats { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px 28px; margin-top: var(--space-lg); color: rgba(255,255,255,.85); font-family: var(--font-heading); font-weight: 500; }
    .rp-stats strong { color: var(--brand-gold); font-weight: 700; }
    .rp-mapwrap { background: var(--gray-100); padding: var(--space-2xl) 0; }
    .rp-head { text-align: center; max-width: 860px; margin: 0 auto var(--space-xl); }
    .rp-head h2 { font: var(--font-section); color: var(--navy-500); margin-top: var(--space-xs); }
    .rp-head p { margin-top: var(--space-sm); color: var(--gray-600, #5b6275); }
    #rpMap { height: 480px; border-radius: var(--radius-xl); overflow: hidden; box-shadow: var(--shadow-md); border: 2px solid var(--white); background: #dfe6ee; }
    @media (max-width: 640px) { #rpMap { height: 360px; } .rp-hero { padding: 150px 0 60px; } .rp-hero-btns a { min-width: 0; flex: 1 1 100%; } }
    .rp-mapnote { margin-top: 12px; font-size: .9rem; color: var(--gray-600, #5b6275); text-align: center; }
    .rp-pin { width: 30px; height: 30px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); background: var(--brand-red); border: 3px solid #fff; box-shadow: 0 3px 10px rgba(21,27,63,.35); }
    .rp-pin.rv { background: var(--brand-navy); }
    .rp-pin::after { content: ''; position: absolute; inset: 7px; border-radius: 50%; background: var(--brand-gold); }
    .leaflet-popup-content { font-family: var(--font-family, sans-serif); margin: 14px 16px; }
    .rp-pop strong { display: block; font-family: var(--font-heading); color: var(--navy-500); font-size: 1rem; }
    .rp-pop span { display: block; color: #5b6275; font-size: .85rem; margin: 2px 0 8px; }
    .rp-pop a { color: var(--brand-red); font-weight: 700; }
    .rp-filters { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; align-items: flex-end; margin-bottom: var(--space-xl); }
    .rp-chips { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; border: 0; padding: 0; margin: 0; }
    .rp-chips legend, .rp-city label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .rp-chip { padding: 12px 22px; border-radius: var(--radius-full); font-family: var(--font-heading); font-weight: 600; font-size: .95rem; color: var(--navy-500); background: var(--white); border: 1.5px solid var(--gray-200); cursor: pointer; transition: background .25s, color .25s, border-color .25s; }
    .rp-chip:hover { border-color: var(--brand-gold); }
    .rp-chip[aria-pressed="true"] { background: var(--brand-red); border-color: var(--brand-red); color: var(--white); }
    .rp-city select { padding: 12px 40px 12px 18px; border-radius: var(--radius-full); border: 1.5px solid var(--gray-200); font-family: var(--font-heading); font-weight: 600; font-size: .95rem; color: var(--navy-500); background: var(--white); }
    .rp-chip:focus-visible, .rp-city select:focus-visible, .rp-card a:focus-visible, .rp-card button:focus-visible, .rp-hero-btns a:focus-visible { outline: 3px solid var(--brand-gold); outline-offset: 3px; }
    .rp-count { text-align: center; color: var(--gray-600, #5b6275); margin: -16px 0 var(--space-lg); font-weight: 600; }
    .rp-grid { display: grid; grid-template-columns: 1fr; gap: var(--space-lg); list-style: none; padding: 0; margin: 0; }
    @media (min-width: 700px) { .rp-grid { grid-template-columns: 1fr 1fr; } }
    @media (min-width: 1100px) { .rp-grid { grid-template-columns: repeat(3, 1fr); } }
    .rp-card { background: var(--white); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-md); display: flex; flex-direction: column; border: 1px solid var(--gray-200); }
    .rp-card[hidden] { display: none; }
    .rp-photos { display: grid; grid-template-columns: 2fr 1fr; grid-template-rows: 1fr 1fr; gap: 3px; aspect-ratio: 4 / 3; background: var(--gray-100); }
    .rp-photos.n1 { grid-template-columns: 1fr; grid-template-rows: 1fr; }
    .rp-photos.n2 { grid-template-rows: 1fr; grid-template-columns: 1fr 1fr; }
    .rp-photos button { padding: 0; border: 0; background: none; cursor: zoom-in; overflow: hidden; min-height: 0; }
    .rp-photos button:first-child { grid-row: span 2; }
    .rp-photos.n2 button:first-child, .rp-photos.n1 button:first-child { grid-row: auto; }
    .rp-photos img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .4s ease; }
    .rp-photos button:hover img { transform: scale(1.04); }
    .rp-nophoto { aspect-ratio: 4 / 3; display: flex; align-items: center; justify-content: center; background: var(--gradient-hero-home); color: var(--brand-gold); }
    .rp-nophoto .material-icons { font-size: 64px; }
    .rp-body { padding: 22px 22px 24px; display: flex; flex-direction: column; gap: 10px; flex: 1; }
    .rp-tag { align-self: flex-start; background: var(--red-050); color: var(--brand-red); font-family: var(--font-heading); font-weight: 600; font-size: .8rem; letter-spacing: .04em; text-transform: uppercase; padding: 5px 12px; border-radius: var(--radius-full); }
    .rp-title { font-family: var(--font-heading); font-weight: 700; font-size: 1.25rem; line-height: 1.25; color: var(--navy-500); }
    .rp-meta { display: flex; flex-wrap: wrap; gap: 6px 16px; color: #5b6275; font-size: .95rem; }
    .rp-meta span { display: inline-flex; align-items: center; gap: 4px; }
    .rp-meta .material-icons { font-size: 1.1rem; color: var(--brand-red); }
    .rp-review { margin: 6px 0 0; padding: 16px 18px; background: var(--gray-100); border-left: 4px solid var(--brand-gold); border-radius: 0 var(--radius-md) var(--radius-md) 0; }
    .rp-stars { color: var(--brand-gold); letter-spacing: 2px; font-size: 1.05rem; }
    .rp-review p { margin: 6px 0 8px; color: var(--navy-700); font-size: 1rem; line-height: 1.6; }
    .rp-review footer { font-size: .88rem; color: #5b6275; display: flex; align-items: center; gap: 6px; }
    .rp-review footer img { width: 16px; height: 16px; }
    .rp-showmap { margin-top: auto; align-self: flex-start; background: none; border: 0; padding: 6px 0 0; color: var(--brand-red); font-family: var(--font-heading); font-weight: 700; font-size: .95rem; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
    .rp-showmap:hover { text-decoration: underline; }
    .rp-cta { margin-top: var(--space-2xl); text-align: center; background: var(--gradient-hero-home); color: #fff; border-radius: var(--radius-xl); padding: var(--space-xl) var(--space-lg); }
    .rp-cta h2 { font: var(--font-section); font-size: clamp(1.6rem, 3vw, 2.25rem); }
    .rp-cta p { color: rgba(255,255,255,.85); margin-top: 10px; }
    #rpZoom { border: 0; padding: 0; background: transparent; max-width: 94vw; max-height: 92vh; }
    #rpZoom::backdrop { background: rgba(10,14,30,.82); }
    #rpZoom img { max-width: 94vw; max-height: 84vh; border-radius: var(--radius-lg); display: block; }
    #rpZoom .rp-zclose { position: absolute; top: 10px; right: 10px; width: 48px; height: 48px; border-radius: 50%; border: 0; background: rgba(21,27,63,.8); color: #fff; font-size: 1.8rem; cursor: pointer; }
    .rp-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  </style>
<!-- RP-HEAD:END -->"""

ICON = {"install": "hvac", "repair": "build", "maintenance": "event_available"}


def fdate(s):
    d = dt.date.fromisoformat(s); return d.strftime("%B %-d, %Y")


def card(p, i):
    n = len(p["photos"])
    alt_base = f'{p["service"]} by Comfort One in {p["city"]}, {p["state"]}'
    if n:
        btns = "".join(
            f'<button type="button" class="rp-zoom" data-src="{E(ph["src"])}" aria-label="Enlarge photo {k+1} of {n}: {E(alt_base)}">'
            f'<img src="{E(ph["src"])}" alt="{E(alt_base)}, photo {k+1}" width="{ph["w"]}" height="{ph["h"]}" loading="{"eager" if i < 3 and k == 0 else "lazy"}" decoding="async" /></button>'
            for k, ph in enumerate(p["photos"]))
        media = f'<div class="rp-photos n{n}">{btns}</div>'
    else:
        media = f'<div class="rp-nophoto" aria-hidden="true"><span class="material-icons">{ICON[p["category"]]}</span></div>'
    rv = ""
    if p.get("review"):
        r = p["review"]; stars = "★" * int(r.get("rating") or 5)
        rv = (f'<blockquote class="rp-review"><div class="rp-stars" aria-label="{int(r.get("rating") or 5)} out of 5 stars">{stars}</div>'
              f'<p>{E(r["text"])}</p><footer><img src="/imag/google-g.svg" alt="" width="16" height="16" />'
              f'{E(r["author"])}, Google review, {E(fdate(r["date"]))}</footer></blockquote>')
    return f'''<li class="rp-card" id="p-{p["id"]}" data-cat="{p["category"]}" data-city="{E(p["city"])}">
        {media}
        <div class="rp-body">
          <span class="rp-tag">{E(p["categoryLabel"])}</span>
          <h3 class="rp-title">{E(p["service"])} in {E(p["city"])}, {E(p["state"])}</h3>
          <div class="rp-meta"><span><span class="material-icons" aria-hidden="true">place</span>{E(p["city"])}, {E(p["state"])}</span><span><span class="material-icons" aria-hidden="true">event</span><time datetime="{p["date"]}">{fdate(p["date"])}</time></span></div>
          {rv}
          <button type="button" class="rp-showmap" data-id="{p["id"]}"><span class="material-icons" aria-hidden="true">map</span>Show on map</button>
        </div>
      </li>'''


def main():
    P = DATA["projects"]
    cities = sorted({p["city"] for p in P})
    cats = [c for c in ("install", "repair", "maintenance") if any(p["category"] == c for p in P)]
    catlabel = {p["category"]: p["categoryLabel"] for p in P}
    nrev = sum(1 for p in P if p.get("review"))
    pins = [{"id": p["id"], "lat": p["lat"], "lng": p["lng"], "t": f'{p["service"]}', "c": f'{p["city"]}, {p["state"]}', "d": fdate(p["date"]), "cat": p["category"], "city": p["city"], "rv": bool(p.get("review"))} for p in P]
    chips = '<button type="button" class="rp-chip" data-cat="all" aria-pressed="true">All projects</button>' + "".join(
        f'<button type="button" class="rp-chip" data-cat="{c}" aria-pressed="false">{E(catlabel[c])}</button>' for c in cats)
    opts = '<option value="all">All cities</option>' + "".join(f'<option value="{E(c)}">{E(c)}</option>' for c in cities)
    main_html = f'''<!-- RP:START -->
  <main id="main">
  <section class="rp-hero gradient-hero" style="background: var(--gradient-hero-home);">
    <div class="container">
      <div class="section-label gold">Real Jobs From Our Technicians</div>
      <h1 class="page-hero-title">Recent HVAC Projects Near You</h1>
      <p class="page-hero-desc">Photos straight from our crews' latest installations, replacements and repairs across Scottsdale, Phoenix and the North Valley, paired with what homeowners said about the work on Google.</p>
      <div class="rp-hero-btns">
        <a href="tel:+16022476151" class="btn-gold"><span class="material-icons" aria-hidden="true">call</span>Call (602) 247-6151</a>
        <a href="/#contact" class="btn-primary">Request a Service</a>
      </div>
      <div class="rp-stats"><span><strong>{len(P)}</strong> recent projects</span><span><strong>{len(cities)}</strong> communities</span><span><strong>{nrev}</strong> matched Google reviews</span></div>
    </div>
  </section>

  <section class="rp-mapwrap" aria-labelledby="rpMapTitle">
    <div class="container">
      <div class="rp-head">
        <div class="section-label" style="justify-content:center;">Project Map</div>
        <h2 id="rpMapTitle">Where we've been working lately</h2>
      </div>
      <div id="rpMap" role="region" aria-label="Map of recent Comfort One projects. The project list below contains the same information."></div>
      <p class="rp-mapnote">Pins show the approximate area of each job, not the home's address, to protect our customers' privacy.</p>
    </div>
  </section>

  <section class="section-padding" style="background: var(--white);" aria-labelledby="rpListTitle">
    <div class="container">
      <div class="rp-head">
        <div class="section-label" style="justify-content:center;">Project Feed</div>
        <h2 id="rpListTitle">Our latest installs, replacements and repairs</h2>
      </div>
      <div class="rp-filters">
        <fieldset class="rp-chips"><legend>Filter by service</legend>{chips}</fieldset>
        <div class="rp-city"><label for="rpCity">Filter by city</label><select id="rpCity">{opts}</select></div>
      </div>
      <p class="rp-count" id="rpCount" role="status" aria-live="polite">Showing {len(P)} projects</p>
      <ul class="rp-grid" id="rpGrid">
      {"".join(card(p, i) for i, p in enumerate(P))}
      </ul>
      <div class="rp-cta">
        <h2>Want your home on this map?</h2>
        <p>Talk to a Comfort One comfort specialist about a repair, replacement or tune-up.</p>
        <div class="rp-hero-btns">
          <a href="tel:+16022476151" class="btn-gold"><span class="material-icons" aria-hidden="true">call</span>Call (602) 247-6151</a>
          <a href="/#contact" class="btn-primary">Request a Service</a>
        </div>
      </div>
    </div>
  </section>
  <dialog id="rpZoom" aria-label="Enlarged project photo"><button type="button" class="rp-zclose" aria-label="Close photo">&times;</button><img alt="" /></dialog>
  </main>
  <script type="application/json" id="rpPins">{json.dumps(pins).replace("</", "<\\/")}</script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin="" defer></script>
  <script defer src="/recent-projects/recent-projects.js"></script>
<!-- RP:END -->'''
    s = PAGE.read_text()
    if "<!-- RP:START -->" not in s:
        s = re.sub(r'  <!-- =+ PLACEHOLDER =+ -->\s*<main[^>]*>.*?</main>', main_html, s, count=1, flags=re.S)
    else:
        s = re.sub(r"<!-- RP:START -->.*?<!-- RP:END -->", lambda m: main_html, s, flags=re.S)
    if "<!-- RP-HEAD:START -->" not in s:
        s = s.replace("</head>", HEAD + "\n</head>", 1)
    else:
        s = re.sub(r"<!-- RP-HEAD:START -->.*?<!-- RP-HEAD:END -->", lambda m: HEAD, s, flags=re.S)
    PAGE.write_text(s)
    print(f"rendered {len(P)} projects into {PAGE}")


if __name__ == "__main__":
    main()
