# Recent Projects page (replaces Real Work widget)

1. `HOUSECALL_PRO_READONLY_MARKETING_KEY=... python3 scripts/sync-hcp.py --max 30`  (read-only GETs; needs Pillow)
2. `python3 scripts/build-recent-projects.py`  (renders static cards into recent-projects/index.html)

- Hide a whole job: add its HCP job id to `data/exclude-jobs.txt`.
- Hide a photo: add the file name (without `.webp`) from `imag/projects/` to `data/exclude-photos.txt`.
- Reviews: `data/google-reviews.json` is a seed of public Google reviews (as already shown on comfort1ac.com).
  When Google Business Profile API access is approved, implement `fetch_gbp_reviews()` in sync-hcp.py.
- Locations are city + coordinates rounded to 0.01° (~1 km). No street addresses or customer names are written.
- The page has `<meta name="robots" content="noindex, nofollow">` while it's a preview; remove it in the RP-HEAD block of build-recent-projects.py at launch.
