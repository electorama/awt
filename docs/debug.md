# Debug System Specification

## Overview

AWT debug system provides JSON debug data for any route via `?debug=json` parameter.

## Usage

Add `?debug=json` to any route to get debug information:
```
/?debug=json
/awt?debug=json
/id/DPL2003?debug=json
/id/DPL2003/IRV?debug=json
/tag/featured?debug=json
/browse?debug=json
```

## Testing with fetch_awt_url.py

- `python3 fetch_awt_url.py --debug '/id/DPL2003'` - Returns HTML with debug info at bottom (server runs in debug mode)
- `python3 fetch_awt_url.py --debug '/id/DPL2003?debug=json'` - Returns JSON debug data

## Access Control

All debug endpoints require `--debug` flag when starting the server. Returns 403 Forbidden if debug mode not enabled.

## Data Structure

### All Routes
- `msgs` dict - Template variables and context data
- `webenv` dict - Web environment variables
- Request timing and cache information (future)

### Election Routes (`/id/<identifier>`)
- `resblob` - Complete election analysis results
- All standard route data (msgs, webenv)

### Other Route Types
- Tag routes: Tag processing info (future)
- Browse routes: Election list metadata (future)

## Template Debug Integration

- Existing template debug info remains at page bottom when debug mode enabled
- Same underlying data available via `?debug=json` API
- Template debug data should inform what's included in JSON response

## Implementation

Use `?debug=json` parameter detection in existing routes rather than separate debug route hierarchy. Routes check for debug parameter and return JSON instead of HTML when present.


## Error Handling

Debug data generation should crash hard on errors to provide clear exception traces for debugging.