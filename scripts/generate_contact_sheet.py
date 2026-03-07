"""Generate an HTML contact sheet for visual review of camera images.

Groups images by source, then by brand. Click any image to see it full-size.
Bad images can be flagged by noting their path.

Usage:
    uv run python scripts/generate_contact_sheet.py
    open data/contact_sheet.html
"""

import json
import re
from pathlib import Path

CAMERAS_FILE = Path("data/merged/cameras.json")
IMAGES_DIR = Path("data/images/cameras")
OUTPUT = Path("data/contact_sheet.html")


def sanitize(name):
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    s = re.sub(r'[\s_]+', '_', s).strip('_.')
    return s[:200] if s else 'unknown'


cameras = json.loads(CAMERAS_FILE.read_text())

# Group by source -> brand -> list of (name, path)
by_source = {}
for cam in cameras:
    imgs = cam.get("images", [])
    if not imgs:
        continue
    img = imgs[0]
    lp = img.get("local_path", "")
    if not lp or not Path(lp).exists():
        continue
    src = img.get("source", "unknown")
    brand = cam.get("manufacturer_normalized", "?")
    name = cam.get("name", "?")
    by_source.setdefault(src, {}).setdefault(brand, []).append((name, lp))

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Camera Image Contact Sheet</title>
<style>
body { font-family: -apple-system, sans-serif; background: #111; color: #eee; margin: 20px; }
h1 { color: #fff; }
h2 { color: #aaf; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 5px; }
h3 { color: #8a8; margin-top: 15px; }
.grid { display: flex; flex-wrap: wrap; gap: 8px; }
.card { background: #222; border-radius: 4px; padding: 4px; width: 180px; text-align: center; }
.card img { width: 180px; height: 130px; object-fit: cover; border-radius: 2px; cursor: pointer; }
.card img:hover { outline: 2px solid #ff0; }
.card .label { font-size: 11px; color: #aaa; margin-top: 4px; word-break: break-all; max-height: 28px; overflow: hidden; }
.stats { color: #888; font-size: 14px; }
</style>
</head>
<body>
<h1>Camera Image Contact Sheet</h1>
<p class="stats">Review images by source. Click to view full size. Flag bad ones by noting the camera name.</p>
"""

# Order sources by risk (most suspect first)
source_order = ["flickr_scrape", "flickr_search", "commons_search", "chinesecamera", "collectiblend", "local", "wikidata"]
for src in source_order:
    if src not in by_source:
        continue
    brands = by_source[src]
    total = sum(len(v) for v in brands.values())
    html += f'<h2>{src} ({total} images)</h2>\n'

    for brand in sorted(brands.keys()):
        items = brands[brand]
        html += f'<h3>{brand} ({len(items)})</h3>\n<div class="grid">\n'
        for name, lp in sorted(items):
            html += f'<div class="card"><a href="{lp}" target="_blank"><img src="{lp}" loading="lazy"></a><div class="label">{name}</div></div>\n'
        html += '</div>\n'

html += """
</body>
</html>
"""

OUTPUT.write_text(html)
print(f"Generated {OUTPUT} ({sum(sum(len(v) for v in brands.values()) for brands in by_source.values())} images)")
