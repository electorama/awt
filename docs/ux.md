# UX Improvement Plan for AWT Election Results

This document outlines an incremental plan for improving the user experience of election results display in the ABIF Web Tool (AWT).

## Overview

The goal is to provide users with two complementary viewing modes:
1. **Long-form view**: Current vertical layout, optimized for printing and comprehensive analysis
2. **Tabbed view**: Interactive tabs showing one voting method at a time for focused comparison

## Implementation Steps

**Current Status**: Steps 1-5 are completed. See `CLAUDE.md` for detailed implementation notes.

### Step 1: Consolidate Condorcet Sections ✅ COMPLETED

**Objective**: Merge the separate "Pairwise diagram" and "Win-loss-tie table" sections into a unified Condorcet section.

**Changes**:
- Create umbrella section titled "Condorcet/Copeland/pairwise results"
- Keep existing subsection names:
  - "Pairwise (Condorcet/Copeland) diagram" 
  - "Win-loss-tie (Condorcet/Copeland) table"
- Maintain current functionality and permalinks
- Update table of contents to reflect consolidated structure

**Files to modify**:
- `templates/results-index.html`
- Update section organization around lines 201-250

### Step 2: ABIF Metadata for Voting System Declaration

**Objective**: Establish a standard way to declare the primary voting system used in an election within ABIF metadata.

**Proposed metadata fields**:
This will actually be two fields: `ballot_type` and `tally_method`.
Most of the work for this should be done in abiftool/abiflib.  See
abiftool/docs/metadata.md for more information.

### Step 3: Dynamic Method Ordering

**Objective**: Reorder voting methods based on declared system or detected ballot format.

**Ordering rules**:

**If `tally_method` declared in metadata**: Put declared system first

**If no declaration**:
- **Ranked ballots detected**: IRV → FPTP → Approval → STAR → Condorcet
- **Non-ranked ballots detected**: FPTP → Approval → IRV → STAR → Condorcet

**Implementation**:
- Create ordering logic function
- Modify template rendering to use dynamic ordering
- Ensure all related UI elements (table of contents, navigation) reflect new order

**Files to modify**:
- `awt.py` (result processing and template context)
- `templates/results-index.html` (dynamic section ordering)

### Step 4: Visual Tab Interface (Static Links)

**Objective**: Convert the current table of contents into visually appealing horizontal tabs while maintaining current link behavior.

**Design requirements**:
- Horizontal tab layout across top of results section
- Tab styling with clear active/inactive states
- Maintain current anchor link functionality (`#fptp`, `#irv`, etc.)
- Ensure accessibility (keyboard navigation, screen readers)
- Responsive design for mobile devices

**Implementation**:
- Update CSS in `static/css/electostyle.css`
- Modify table of contents HTML structure in `templates/results-index.html`
- Style tabs to look clickable and professional
- Ensure visual hierarchy is clear

**CSS classes to add**:
```css
.method-tabs
.method-tab
.method-tab.active
.method-tab:hover
```

### Step 5: Interactive Tabbed View ✅ COMPLETED

**Objective**: Provide toggle between long-form and tabbed viewing modes.

**Implementation completed**:
- Toggle control positioned next to winner table
- JavaScript-based view mode switching (CSS-only proved insufficient)
- Tabbed mode shows one method at a time with active tab highlighting
- Long-form mode hides tabs and shows all content (print-friendly)
- Winner table links behave differently in each mode
- URL fragment navigation maintained

**Key files modified**:
- `templates/results-index.html` - Added toggle control and tabbed structure
- `static/css/electostyle.css` - Added tabbed interface styling
- `static/js/abifwebtool.js` - Added view mode switching logic

### Step 6: Enhanced Result Visibility

**Objective**: Make it very easy to see the essence of the results quickly toggling in the tabbed interface.

- Consider placing winning candidate color boxes in the tab label for
  each election method
- Place a bulleted list with the essense of the results at the top of
  the results for each method, with "* <method> Winner: <winner>"
  bolded at the top of the list.  The list should be modeled after the
  current IRV/RCV results, and MAYBE have a few other stats besides
  the winner, but no more than six or so bullets.
- Deep in the results for all methods, the "✅" symbol should be next
  to the winner so that it's easy to visually scan for the winner
- Swap the "Win-loss-tie (Condorcet/Copeland) table" and "Pairwise
  (Condorcet/Copeland) diagram" subsections so that the latter is
  above the former in the "Condorcet/Copeland" section.
- Put a bulleted list in the "Condorcet/Copeland" section above the subsections
- There should be a "🔗http://awt.electorama.com/id/Burl2009/pairwise"
  link at the top of the Condorcet/Copeland/pairwise section
- Shorten "Condorcet/Copeland/pairwise" to "Condorcet/Copeland" in
  some places - particularly for section headers where "pairwise"
  already appears in subsection titles. Keep "pairwise" terminology
  in URLs, prose, and places where it's the most descriptive term.
- Deprecate the "wlt" abbreviation
- Come up with a slick accordian view for elections with stupidly wide
  tables (e.g. /id/sf2024-mayor )

### Step 7: URL hackability/stability/maintainability

**Objective**: have forgiving URLs (e.g. case-insensitivity where
  appropriate) while having a maintainable list

- Make it possible to deprecate URLs without breaking them
- Have a clean, performant layer of redirects that is easy to add to
- Have a URL strategy to make it so that some /id/* URLs can be
  deprecated with a clean redirect to the correct URL
- Possibly replicate MediaWiki's post-redirect user interface, where
  there's a discreet note at the top of the page about the current
  page being redirected from the original URL.
- URL state preservation for tabbed mode

## Technical Considerations

### Backward Compatibility
- All existing URLs and permalinks must continue to work
- Print styles should remain optimized for long-form view
- Graceful degradation for users without JavaScript

### Performance
- CSS-based solution should have minimal performance impact
- Consider lazy loading of complex visualizations in tabbed mode

### Accessibility
- Maintain ARIA labels and keyboard navigation
- Ensure screen reader compatibility
- High contrast support for visual elements

### Testing Strategy
- Test with various election data sets
- Verify print formatting remains intact
- Cross-browser compatibility testing
- Mobile responsiveness validation


