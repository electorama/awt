# UX Improvement Plan for AWT Election Results

This document outlines an incremental plan for improving the user experience of election results display in the ABIF Web Tool (AWT).

## Overview

The goal is to provide users with two complementary viewing modes:
1. **Long-form view**: Current vertical layout, optimized for printing and comprehensive analysis
2. **Tabbed view**: Interactive tabs showing one voting method at a time for focused comparison

## Implementation Steps

### Step 1: Consolidate Condorcet Sections

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

**If `voting_system` declared in metadata**: Put declared system first

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

### Step 5: Interactive Tabbed View

**Objective**: Provide CSS-based toggle between long-form and tabbed viewing modes.

**Requirements**:
- **Primary goal**: Pure CSS solution if possible
- Toggle control to switch between "Long-form view" and "Tabbed view"
- In tabbed mode, show only one method's content at a time
- Preserve printability of long-form view
- Maintain URL fragment navigation (`#irv`, etc.)

**CSS-only approach**:
- Use CSS `:target` pseudo-class for tab switching
- Radio button technique with hidden inputs for mode switching
- CSS-only show/hide logic for content sections

**Minimal JavaScript fallback**:
- Only if CSS-only proves insufficient for smooth UX
- Simple toggle function for view mode
- Tab switching event handlers

**Implementation**:
- Extend CSS with tabbed view styles
- Add view mode toggle control to template
- Test thoroughly across browsers
- Ensure degradation for non-JavaScript environments

**CSS classes to add**:
```css
.view-mode-toggle
.results-container.long-form
.results-container.tabbed
.method-content.visible
.method-content.hidden
```

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

## Success Metrics

1. **Usability**: Users can easily switch between viewing modes
2. **Performance**: No significant slowdown in page load or interaction
3. **Compatibility**: All existing functionality preserved
4. **Accessibility**: Meets WCAG guidelines for interactive elements
5. **Print-friendly**: Long-form view prints cleanly without layout issues

## Future Enhancements (Post-Implementation)

- Keyboard shortcuts for tab navigation (J/K keys, arrow keys)
- URL state preservation for tabbed mode
- Customizable method ordering via user preferences
- Method comparison mode (side-by-side view)
- Export functionality for individual method results