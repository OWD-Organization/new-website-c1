#!/usr/bin/env python3
"""Sync recent Comfort One jobs from Housecall Pro into data/recent-projects.json.

READ-ONLY: this script only issues HTTP GET requests to the Housecall Pro API.

  HOUSECALL_PRO_READONLY_MARKETING_KEY=... python3 scripts/sync-hcp.py [--days 150] [--max 24]

What it does
  1. Pulls completed jobs (newest first) with their photo attachments.
  2. Downloads up to N photos per job (signed URLs expire after ~1h), applies EXIF
     rotation, strips ALL metadata (incl. GPS), resizes, and saves WebP to /imag/projects/.
  3. Loads Google reviews from data/google-reviews.json (seed) or, once access is
     granted, from the Google Business Profile API (see fetch_gbp_reviews hook).
  4. Matches each review to a job (customer initials + first name from the owner's
     reply when present + review posted 0-21 days after the job was completed).
  5. Writes data/recent-projects.json with APPROXIMATE locations only: city + coordinates
     rounded to 0.01 deg (~1 km). No street addresses, no customer names are written.
Then run scripts/build-recent-projects.py to render the static HTML.
"""
import argparse, datetime as dt, hashlib, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://api.housecallpro.com"
IMG_DIR = ROOT / "imag" / "projects"
OUT = ROOT / "data" / "recent-projects.json"
REVIEWS_SEED = ROOT / "data" / "google-reviews.json"


def key():
    k = os.environ.get("HOUSECALL_PRO_READONLY_MARKETING_KEY")
    if not k:
        sys.exit("HOUSECALL_PRO_READONLY_MARKETING_KEY is not set")
    return k


def hcp_get(path, params=None, tries=6):
    """GET only. Retries on 429/5xx."""
    url = BASE + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for i in range(tries):
        req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Token {key()}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(min(30, 2 ** i)); continue
            raise
    raise RuntimeError(f"HCP GET failed: {path}")


def completed_jobs(since):
    page = 1
    while True:
        d = hcp_get("/jobs", {"page": page, "page_size": 100, "sort_direction": "desc",
                              "work_status[]": "completed", "expand[]": "attachments"})
        jobs = d.get("jobs", [])
        if not jobs:
            return
        oldest = None
        for j in jobs:
            c = (j.get("work_timestamps") or {}).get("completed_at")
            if not c:
                continue
            cd = dt.datetime.fromisoformat(c.replace("Z", "+00:00"))
            oldest = cd if oldest is None or cd < oldest else oldest
            if cd >= since:
                yield j
        if page >= d.get("total_pages", 1) or (oldest and oldest < since - dt.timedelta(days=30)):
            return
        page += 1


# ---------- service classification (public-facing labels only) ----------
RULES = [
    (r"mini.?split|ductless", "Ductless Mini Split", "install"),
    (r"heat pump.*(ton|seer)|(ton|seer).*heat pump", "Heat Pump System Installation", "install"),
    (r"\bfurnace\b.*(install|replace|ton|btu)", "Furnace Replacement", "install"),
    (r"\bton\b.*seer|seer.*\bton\b|\bsystem (install|replacement)", "AC System Replacement", "install"),
    (r"air handler", "Air Handler Replacement", "repair"),
    (r"\bcoil\b.*replac|replac.*\bcoil\b", "Evaporator Coil Replacement", "repair"),
    (r"thermostat", "Thermostat Installation", "repair"),
    (r"condensate", "Condensate Leak Repair", "repair"),
    (r"tune.?up|maintenance|pre-season", "AC Tune-Up & Maintenance", "maintenance"),
    (r"blower", "Blower Repair", "repair"),
    (r"capacitor|mfd|contactor|control board|defrost|motor", "AC Repair", "repair"),
    (r"r-?410|r-?22|refrigerant|freon|leak", "AC Repair", "repair"),
]
TYPE_FALLBACK = {"Repair": ("AC Repair", "repair"), "Maintenance": ("AC Tune-Up & Maintenance", "maintenance"),
                 "Install": ("AC System Replacement", "install"), "Condensate": ("Condensate Leak Repair", "repair"),
                 "Diagnostic": ("HVAC Diagnostic", "repair")}
CATEGORY_LABEL = {"install": "Installation & Replacement", "repair": "Repair", "maintenance": "Maintenance"}


def classify(job):
    text = (job.get("description") or "").lower()
    for pat, label, cat in RULES:
        if re.search(pat, text):
            return label, cat
    jt = (((job.get("job_fields") or {}).get("job_type") or {}).get("name") or "").strip()
    return TYPE_FALLBACK.get(jt, ("HVAC Service", "repair"))


def initials(first, last):
    f = (first or "").strip()[:1].upper(); l = (last or "").strip()[:1].upper()
    return f"{f}. {l}." if f and l else None


# ---------- Google reviews ----------
def fetch_gbp_reviews():
    """HOOK: once Google approves Business Profile API access, implement here:
       GET https://mybusiness.googleapis.com/v4/accounts/{acct}/locations/{loc}/reviews
       (OAuth as a Manager of the profile). Return a list shaped like data/google-reviews.json
       entries: {id, author (as Google shows it), rating, text, date (YYYY-MM-DD), reply, source:'google'}.
       Return None to fall back to the seed file."""
    return None


def load_reviews():
    r = fetch_gbp_reviews()
    if r is not None:
        return r
    return json.loads(REVIEWS_SEED.read_text())["reviews"] if REVIEWS_SEED.exists() else []


def match_reviews(jobs, reviews):
    """Return {job_id: review}. Rules: initials must match the HCP customer; if the owner's
    reply names the reviewer, the first name must match too; review must be posted 0-21 days
    after completion. Ambiguous matches (2+ candidate jobs) are skipped."""
    out = {}
    for rv in reviews:
        rdate = dt.date.fromisoformat(rv["date"])
        ini = (rv.get("author") or "").upper().replace(" ", "")
        reply_first = None
        m = re.match(r"\s*(?:Thank you,?\s+|Thanks,?\s+)?([A-Z][a-z]+)\b", rv.get("reply") or "")
        if m and m.group(1) not in {"Thank", "Thanks", "We", "It", "Hi", "Hello", "Dear", "Wow", "Your", "What", "Our"}:
            reply_first = m.group(1).lower()
        cands = []
        for j in jobs:
            c = j["_completed"].date()
            if not (0 <= (rdate - c).days <= 21):
                continue
            cu = j.get("customer") or {}
            if (initials(cu.get("first_name"), cu.get("last_name")) or "").replace(" ", "") != ini:
                continue
            if reply_first and (cu.get("first_name") or "").strip().lower().split(" ")[0] != reply_first:
                continue
            cands.append(j)
        # same customer can have several visits; take the latest before the review
        custs = {(j.get("customer") or {}).get("id") for j in cands}
        if len(custs) == 1:
            best = max(cands, key=lambda j: j["_completed"])
            out.setdefault(best["id"], rv)
    return out


# ---------- photos ----------
def photo_score(im):
    """Higher = more 'real job site' looking. Screenshots, drawings and data-plate
    close-ups (mostly white/grey, text heavy) score low."""
    w, h = im.size
    if max(w, h) / min(w, h) > 1.9:          # phone screenshots
        return -1
    sm = im.copy(); sm.thumbnail((96, 96))
    px = list(sm.get_flattened_data()); n = len(px)
    white = sum(1 for r, g, b in px if r > 215 and g > 215 and b > 215) / n
    rg = [r - g for r, g, b in px]; yb = [0.5 * (r + g) - b for r, g, b in px]
    def sd(v):
        m = sum(v) / len(v); return (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5
    colorful = (sd(rg) ** 2 + sd(yb) ** 2) ** 0.5 + 0.3 * ((sum(rg) / n) ** 2 + (sum(yb) / n) ** 2) ** 0.5
    if white > 0.45:                          # drawings, labels, paperwork
        return -1
    return colorful - 40 * white


def save_photos(job, n, excluded_photos=()):
    from PIL import Image, ImageOps
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    cands = []
    imgs = [a for a in (job.get("attachments") or []) if (a.get("file_type") or "").startswith("image/")]
    for a in imgs[:12]:
        h = hashlib.sha1(a["id"].encode()).hexdigest()[:12]
        if h in excluded_photos:
            continue
        rel = f"/imag/projects/{h}.webp"
        dest = ROOT / rel.lstrip("/")
        try:
            if dest.exists():
                im = Image.open(dest).convert("RGB")
            else:
                with urllib.request.urlopen(a["url"], timeout=60) as r:
                    raw = r.read()
                im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
                im.thumbnail((1200, 1200))
        except Exception as e:
            print("photo failed", a["id"], e, file=sys.stderr); continue
        sc = photo_score(im)
        if sc > 8:
            cands.append((sc, rel, dest, im))
    cands.sort(key=lambda c: -c[0])
    out = []
    for sc, rel, dest, im in cands[:n]:
        if not dest.exists():
            im.save(dest, "WEBP", quality=72, method=6)  # no exif= -> metadata (incl. GPS) stripped
        out.append({"src": rel, "w": im.size[0], "h": im.size[1]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--max", type=int, default=24, help="max project cards")
    ap.add_argument("--photos", type=int, default=3)
    ap.add_argument("--min-photos", type=int, default=2)
    ap.add_argument("--exclude", default=str(ROOT / "data" / "exclude-jobs.txt"), help="job ids to hide (one per line)")
    a = ap.parse_args()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)
    excl = set(Path(a.exclude).read_text().split()) if Path(a.exclude).exists() else set()
    exp = ROOT / "data" / "exclude-photos.txt"   # photo hashes (file name without .webp) to hide
    excl_ph = set(exp.read_text().split()) if exp.exists() else set()

    jobs = []
    for j in completed_jobs(since):
        j["_completed"] = dt.datetime.fromisoformat(j["work_timestamps"]["completed_at"].replace("Z", "+00:00"))
        jobs.append(j)
    print(f"HCP completed jobs in window: {len(jobs)}", file=sys.stderr)
    reviews = load_reviews()
    matched = match_reviews(jobs, reviews)
    print(f"reviews: {len(reviews)}, matched to jobs: {len(matched)}", file=sys.stderr)

    def usable(j):
        addr = j.get("address") or {}
        n = sum(1 for x in (j.get("attachments") or []) if (x.get("file_type") or "").startswith("image/"))
        return j["id"] not in excl and addr.get("latitude") and addr.get("city") and n >= a.min_photos

    pool = [j for j in jobs if usable(j)]
    # priority: review-matched first, then installs/replacements, then newest
    pool.sort(key=lambda j: (j["id"] not in matched, classify(j)[1] != "install", -j["_completed"].timestamp()))
    seen_cust, chosen = set(), []
    for j in pool:
        cid = (j.get("customer") or {}).get("id")
        if cid in seen_cust:
            continue
        seen_cust.add(cid); chosen.append(j)
        if len(chosen) >= a.max:
            break
    chosen.sort(key=lambda j: -j["_completed"].timestamp())

    projects = []
    for j in chosen:
        addr = j["address"]; label, cat = classify(j)
        photos = save_photos(j, a.photos, excl_ph)
        rv = matched.get(j["id"])
        if not photos and not rv:   # review-matched jobs stay even without a usable photo
            continue
        projects.append({
            "id": hashlib.sha1(j["id"].encode()).hexdigest()[:10],  # opaque, not the HCP id
            "service": label, "category": cat, "categoryLabel": CATEGORY_LABEL[cat],
            "city": addr["city"].strip().title(), "state": addr.get("state") or "AZ",
            "date": j["_completed"].date().isoformat(),
            "lat": round(float(addr["latitude"]), 2), "lng": round(float(addr["longitude"]), 2),
            "photos": photos,
            "review": ({k: rv.get(k) for k in ("author", "rating", "text", "date", "source", "reply", "replyDate")} if rv else None),
        })
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                               "source": "housecallpro", "reviewSource": "gbp-api" if fetch_gbp_reviews() is not None else "seed",
                               "projects": projects}, indent=2))
    print(f"wrote {len(projects)} projects ({sum(1 for p in projects if p['review'])} with reviews) -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
