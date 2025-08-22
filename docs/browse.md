# Browse Route Implementation

## Implemented in 0.33

`/browse` route with hardcoded tag browser.

### Tag Browser Structure
- By State: e.g. AK, CA, NY, MN, WA (with actual tag names in quotes)
- By Year: 2002-2025 in reverse chronological order
- Misc tags: e.g. actual, theoretical, etc.
- All tags link at bottom

### Implementation Details
- Featured elections section before complete list
- Fancier election list than the old '/id' list

### Key files
- `abif_list.yml`: This file should get replaced in the future bifhub refactor
- `awt.py`: We may want to break out `src/browse.py` in the future
- `templates/tag-browser-snippet.html`: Hardcoded tag categories for now
- `templates/browse-index.html`: Tag browser + featured elections + full list  
- `static/css/electostyle.css`: Minimal styling for tag browser and featured
  sections

## Future Implementation Plans

### Post‑0.33: Dynamic Tag Counts + Manual Categories
- Add dynamic tag counting to show current election counts next to each tag link.
  Example: `<a href="/tag/CA">California ("CA") (95)</a>`
