# Link previews for awt

Emit Open Graph metadata and provide stable 1200×630 images (PNG from an SVG frame) with caching.

* Start with static/img/awt-electorama-linkpreview-frame.svg
* Added candidate names and colorboxes
* create resulting png (or other raster image usable by most socal websites)

- Platforms: Facebook, Slack, Discord
- Coverage: Ideally, all routes/URLs require previews, particularly eleciton pages
- Content in image: Include candidate names/colors.  Up to 4 names before truncation/ellipsis rules
- Rendering: Server-side SVG→PNG (e.g., CairoSVG)
- Fonts: Preferrably free/libre fonts
- Hosting: Where to serve images from (`static/`, CDN), required URL stability, cache-busting scheme?
- Caching: same as with the rest of awt.

## Status

- Metadata set in `templates/base.html` (`og:title`, `og:description`, `og:url`, `og:image`).
- Image routes: `/preview-img/site/generic.png`, `/preview-img/id/<election_id>.png` (CairoSVG PNG; 302 to frame SVG if unavailable). Cached via Flask‑Caching.
- Image content from conduits (no recomputation in templates):
  - Consensus: one large winner line + smaller runners (FPTP order).
  - Disagreement: stacked IRV, FPTP, Approval, STAR, Condorcet/Copeland with brief figures.
- Frame: `static/img/awt-electorama-linkpreview-frame.svg` has a white background.

## Testing

- Start server: `AWT_STATUS=debug AWT_CACHE_TYPE=none python3 awt.py --debug` (or `awt --debug --caching=none` after install) and note the base URL.
- View HTML head: open an election page and inspect `<meta property="og:*">` tags; confirm `og:title`, `og:description`, `og:url`, and `og:image` are present and correct.
- Command-line check:
  - `curl -s <URL> | rg 'og:(title|description|url|image)' -n`
  - `curl -sI <BASE>/preview-img/id/Burl2009.png` to verify `200` (or `302` → SVG) and headers.
- Image dimensions: download the image and check it is 1200x630 (or configured size). If ImageMagick is available: `identify -format "%wx%h\n" preview.png`.
- Caching behavior: reload the image URL twice; confirm second fetch is fast and returns cache headers if caching is enabled.
- Validators (optional):
  - Facebook Sharing Debugger: paste the page URL and Scrape Again to see OG output.
  - Slack/Discord: paste the link in a test channel and verify the unfurl (they honor OG tags).
- Fallbacks: test an election with >4 candidates; verify truncation/"+N more" behavior. Test missing/invalid data and confirm generic preview.

## Refactor Plan (brief)

- Keep `awt.py` as a thin route layer; move preview logic to `src/linkpreview.py` (done).
- See refactor.md for broader refactoring plan.
