# Lightbox Modal Design Documentation

## Overview

The AWT lightbox modal system provides click-to-expand functionality for preview images on election results pages. When users click a preview image in the sidebar, it opens in a full-screen modal overlay for detailed viewing.

## Features

- **Click-to-expand**: Preview images open in full-screen overlay
- **Multiple close methods**: X button, Esc key, click-outside, browser back button
- **URL integration**: Adds `#modal` hash for back button support
- **Responsive display**: Modal adapts to different screen sizes
- **Captions**: Shows descriptive text below expanded image
- **Format switcher**: Sticky SVG/PNG toggle in the modal header

## Implementation

**File**: `static/js/abifwebtool.js`

**HTML Structure**:
```html
<div id="image-modal" class="image-modal">
  <div class="modal-content">
    <div class="modal-header">
      <div class="format-switcher">
        <button class="format-btn active" data-format="svg">SVG</button>
        <button class="format-btn" data-format="png">PNG</button>
      </div>
      <button class="modal-close">&times;</button>
    </div>
    <img src="..." alt="Expanded election preview">
    <p class="modal-caption">Caption text</p>
    <p class="modal-instructions">Press Esc to close</p>
  </div>
</div>
```

## Event Handling

**Close Methods**:
1. **X Button**: `onclick="closeImageModal()"` on close button
2. **Esc Key**: Document-level keydown listener for Escape key
3. **Click Outside**: Click listener on overlay and empty modal padding
4. **Browser Back**: Popstate listener removes modal when navigating back

**Click-Outside Logic**:
```javascript
// Overlay (backdrop) click
modal.addEventListener('click', (e) => {
  if (e.target === modal || !modal.querySelector('.modal-content').contains(e.target)) {
    closeImageModal();
  }
});

// Click on empty areas of the content container (its own padding/background)
const modalContent = modal.querySelector('.modal-content');
modalContent.addEventListener('click', (e) => {
  if (e.target === modalContent) {
    closeImageModal();
  }
});
```

## Activation

**Trigger**: `onclick="openImageModal(this.src, 'caption text')"` on preview images

**Location**: Preview images in election page sidebars (`templates/results-index.html`)

## CSS Styling

**File**: `static/css/electostyle.css`

**Key Classes**:
- `.image-modal` - Full-screen overlay; flex container centers content
- `.modal-content` - Scrollable container (`max-height: 90vh; overflow-y: auto`)
- `.modal-header` - Sticky header (`position: sticky; top: 0`) with controls
- `.format-switcher`/`.format-btn` - SVG/PNG toggle styling
- `.modal-close` - X button styling
- `.modal-caption` - Caption text below image
- `.modal-instructions` - "Press Esc to close" helper text

## URL Integration

- **Hash Addition**: `history.pushState()` adds `#modal` to URL when opening
- **Back Button**: Popstate listener detects navigation and closes modal
- **Hash Removal**: `history.back()` when closing via other methods

## Troubleshooting

**Common Issues**:
1. Click-outside not working: Ensure overlay fills viewport and `.modal-content` doesn’t cover it
2. Header clipped: Confirm `.modal-content` uses `max-height` with scroll and header is sticky
3. Back button/hash: Verify `pushState`/`popstate` aren’t overridden elsewhere

**CSS Requirements**:
- Overlay covers full viewport and centers content
- Content doesn’t consume full overlay height; allow backdrop/padding clicks
- Sticky header remains visible; sufficient z-index

## Test URLs

- **Main test**: `/id/Burl2009` (ABIF checked into abiftool testdata)
- **Copeland tie test**: `/id/2021-11-02_Minneapolis-2021-Ward-2-Cast-Vote-Record`
- **Preview image**: Click the preview image in the sidebar to open lightbox

## Architecture Notes

**Dynamic Creation**: Modal HTML is created programmatically in JavaScript rather than existing in the initial page markup. This ensures only one modal instance and reduces initial page weight.

**Event Listener Scope**: Event listeners are added only once when the modal is first created, not on each open/close cycle.

**State Management**: Modal visibility controlled via `style.display` rather than CSS classes.

## Related Files

1. **`static/js/abifwebtool.js`** - Core modal logic and event handling
2. **`static/css/electostyle.css`** - Modal styling and overlay appearance
3. **`templates/results-index.html`** - Image click triggers and modal activation

## Development Notes

- Introduced in awt 0.34.
- Modal HTML is created once and re-used; listeners attach only on first open.
- Default image format is SVG; the header switcher toggles between SVG and PNG.
