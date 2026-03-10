# Image Sourcing Notes (2026-03-09)

## Current Status
- 10,556 total cameras
- 7,844 with images on disk
- 2,712 without images
- Most missing cameras are legit models from collectiblend (URLs 404'd after site restructure)

## Source Quality Assessment

### Wikidata / Wikipedia / Wikimedia Commons
- **Wikidata P18**: Most reliable, but only works for cameras with QIDs (minority)
- **Wikipedia article images**: Good quality, but limited coverage for obscure models
- **Commons search**: Very unreliable for obscure cameras. Returns unrelated images (e.g., "Bananas in Pyjamas" photo for a Bananas brand camera, Hasselblad for Great Wall). Only useful when camera name is unique enough to match exactly.
- **Verdict**: Already exhausted in previous runs. Remaining 2,712 cameras don't have hits here.

### Flickr Scrape
- Scrapes camera collector groups (Old Film Cameras, Camera Appreciation, Your Camera Collection)
- Quality is mixed — some correct, many are wrong cameras or photos taken BY the camera not OF it
- Of 6 stale flickr_scrape refs checked: Bell BF35 was correct, others were wrong models (Leica M1 for Fotoman, Minolta SRT-101 for AstrHori, etc.)
- Requires Scrapling (headless browser), slow

### DuckDuckGo Image Search
- No API key needed, uses vqd token flow
- **Very unreliable**: returns anything matching keywords loosely
- Examples of bad results:
  - "Haking H400" -> person in a mask, Hikvision security camera, Dahua CCTV
  - "Fotoman" -> Leica M1
- Not suitable for automated bulk downloading without vision-model verification

### eBay Listings
- Searches eBay film cameras category (sacat=15230)
- **Better than DDG** — at least returns real cameras, not random junk
- Accuracy: ~30% exact model match, ~40% right brand/wrong model, ~30% completely wrong
- Examples:
  - DS-Max PN-955: 5/8 correct, 3/8 were PN-338 (same brand, different model)
  - Keystone Easy Shot 400X: correct (in retail packaging)
  - Huashan DF-S: completely wrong (returned Canon Autoboy S)
  - Luxon 110 FF: wrong (returned Minolta Zoom 110)
- Needs realistic browser headers to avoid 503 (Sec-Fetch-* headers required)
- Not accurate enough for unsupervised bulk download

### Collectiblend
- Was the best source — direct product photos for ~5,800 cameras
- Site restructured, ~2,500 image URLs now return 404
- URL format: `https://collectiblend.com/Cameras/images/{URL_brand}-{page_model}.jpg`
- Worth checking periodically if they fix their URL structure

## Recommendations
1. **Vision model verification**: Download from eBay/DDG, then use a vision model to verify the image matches the camera name. Reject mismatches.
2. **Collectiblend recovery**: Monitor if their URLs come back or find new URL patterns
3. **Manual curation**: For high-value cameras, manually source from camera collector sites (mikeeckman.com, cameraquest.com, etc.)
4. **Camera collector databases**: Try scraping dedicated sites like camera-wiki.org, collection-appareils.fr

## Code References
- `src/images/download.py` — Main download pipeline with waterfall search
- `src/images/web_search.py` — DuckDuckGo + eBay search (added 2026-03-09)
- `src/images/flickr_search.py` — Flickr group scraper
- `src/images/museum_search.py` — Smithsonian + Science Museum Group APIs
- Download waterfall currently set to: eBay only (Wikidata/Wikipedia/Commons/Flickr commented out)
