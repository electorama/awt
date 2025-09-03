# Lightbox Modal Design Documentation

## Overview

The AWT lightbox modal system provides click-to-expand functionality for preview images on election results pages. When users click a preview image in the sidebar, it opens in a full-screen modal overlay for detailed viewing.

## Features

- **Click-to-expand**: Preview images open in full-screen overlay
- **Multiple close methods**: X button, Esc key, click-outside, browser back button
- **URL integration**: Adds `#modal` hash for back button support
- **Responsive display**: Modal adapts to different screen sizes
- **Captions**: Shows descriptive text below expanded image

## Implementation

**File**: `static/js/abifwebtool.js` (lines 176-239)

**HTML Structure**:
```html
<div id="image-modal" class="image-modal">
  <div class="modal-content">
    <button class="modal-close">&times;</button>
    <img src="..." alt="Expanded election preview">
    <p class="modal-caption">Caption text</p>
    <p class="modal-instructions">Press Esc to close</p>
  </div>
</div>
```

**Current Click Handler**:
```javascript
modal.addEventListener('click', function(e) {
  if (e.target === modal || !modal.querySelector('.modal-content').contains(e.target)) {
    closeImageModal();
  }
});
```

## Event Handling

**Close Methods**:
1. **X Button**: `onclick="closeImageModal()"` on close button
2. **Esc Key**: Document-level keydown listener for Escape key
3. **Click Outside**: Click listener on modal background
4. **Browser Back**: Popstate listener removes modal when navigating back

**Click-Outside Logic**:
```javascript
modal.addEventListener('click', function(e) {
  if (e.target === modal || !modal.querySelector('.modal-content').contains(e.target)) {
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
- `.image-modal` - Full-screen overlay with dark background
- `.modal-content` - Centered container for image and controls
- `.modal-close` - X button styling
- `.modal-caption` - Caption text below image
- `.modal-instructions` - "Press Esc to close" helper text

## URL Integration

- **Hash Addition**: `history.pushState()` adds `#modal` to URL when opening
- **Back Button**: Popstate listener detects navigation and closes modal
- **Hash Removal**: `history.back()` when closing via other methods

## Troubleshooting

**Common Issues**:
1. **Click-outside not working**: Check CSS overlay coverage and event propagation
2. **Caption display**: Verify `modal-caption` element exists and has content
3. **Back button**: Ensure hash management doesn't conflict with other hash usage
4. **Multiple modals**: System assumes single modal instance per page

**Debugging Tools**:
- Browser dev tools to inspect modal DOM structure when open
- Console.log click targets: `console.log('Clicked:', e.target, e.target.className)`
- Check CSS computed styles for overlay positioning

**CSS Requirements**:
- Modal overlay must cover full viewport
- Modal content should be centered and not cover entire overlay
- Z-index should be higher than other page elements

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

## Development History

The lightbox was added in awt 0.34.
