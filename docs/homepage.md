# Homepage and Edit Interface Separation Design

## Current State (Pre-0.33)

The current `/` route redirects to `/awt`, which serves dual purposes:
1. **Homepage**: Welcome message, featured elections, full election list
2. **Edit Interface**: Form for uploading/pasting ABIF data for analysis

This creates UX confusion where users land on an upload form rather than a proper homepage.

## Proposed Changes

### 0.33: Minimal Homepage Split with /edit Migration

**Conservative approach for Tuesday release:**

1. **New `/` route**: Clean homepage focused on discovery and guidance
   - Uses `templates/homepage-snippet.html` (not index.html - snippet approach for modular content)
   - Welcome message explaining AWT's purpose
   - Two primary actions: "Browse Elections" → `/browse` and "Analyze Your Election" → `/edit`
   - Minimal, focused design

2. **New `/edit` route**: Future-focused edit interface
   - **For 0.33**: Simple redirect to `/awt` to maintain functionality
   - **Future**: Will become the primary upload/analysis interface with simplified tutorial
   - **Long-term**: `/awt` will be deprecated in favor of `/edit`

3. **Extract featured elections**: Create `templates/featured-snippet.html`
   - Modular component for featured elections display
   - Can be reused on homepage, browse page, or other discovery interfaces
   - Clean separation of concerns

4. **Preserve `/awt` route**: Keep existing interface unchanged for 0.33
   - All current functionality preserved
   - Gradual deprecation path planned for future releases
   - Existing bookmarks and links continue working

### Implementation for 0.33

**Files to create/modify:**
- `awt.py`: Add `/` route using homepage-snippet, add `/edit` redirect to `/awt`
- `templates/homepage-snippet.html`: New minimal homepage content
- `templates/featured-snippet.html`: Extracted featured elections component
- `templates/browse-index.html`: Update to use featured-snippet.html
- Update navigation to point to `/edit` instead of `/awt`

**Route structure:**
```
/           → New minimal homepage (uses homepage-snippet.html)
/edit       → Redirect to /awt (0.33), future simplified tutorial interface
/awt        → Existing upload/edit interface (preserved, eventually deprecated)
/browse     → Tag browser + full election list
/id/<id>    → Election analysis results
/tag/<tag>  → Tag-filtered elections
```

### Future Versions (0.34+)

**Enhanced Homepage (0.34):**
- Dynamic featured elections from bifhub
- Recent elections section
- Popular tags widget
- Search functionality
- Better visual design

**Advanced Edit Interface (0.34+):**
- **Replace `/edit` redirect with full tutorial interface**
- Simplified step-by-step ABIF creation tutorial
- Format detection and conversion helpers
- Preview before analysis
- Example templates for common election types
- Clear explanations of ABIF format requirements
- Multi-step wizard for election upload
- Integration with bifhub for saving elections

**Deprecation Timeline:**
- **0.33**: `/edit` redirects to `/awt`, navigation updated
- **0.34**: `/edit` becomes full tutorial interface, `/awt` still functional
- **0.35**: `/awt` shows deprecation notice, encourages `/edit` usage
- **0.36**: `/awt` route removed, redirects to `/edit`

**Unified Design System (0.35+):**
- Consistent navigation across all routes
- Responsive design patterns
- Accessibility improvements
- Mobile-optimized interfaces

## Design Principles

### 0.33 Constraints
- **Zero breaking changes**: All existing URLs must work
- **Minimal risk**: Reuse existing templates and logic where possible
- **Quick implementation**: Should take <2 hours to implement and test
- **Preserve functionality**: No feature removal, only reorganization

### User Experience Goals
- **Clear purpose**: Homepage immediately explains what AWT does
- **Guided discovery**: Easy path to browse existing elections
- **Obvious action**: Clear way to analyze new elections
- **No confusion**: Separate concerns of browsing vs. uploading

### Technical Goals
- **SEO friendly**: Homepage optimized for search engines
- **Performance**: Fast loading, minimal dependencies
- **Maintainable**: Clean separation of concerns
- **Testable**: Easy to verify both routes work correctly

## Implementation Notes

### Content Strategy
- Homepage should explain AWT's value proposition clearly
- Featured elections should showcase diverse voting methods
- Links should use descriptive text, not generic "click here"
- Consider brief voting method explanations

### Template Inheritance
- Both homepage and edit interface should extend `base.html`
- Shared components (featured elections) should be extracted to snippets
- Consistent styling across all pages

### URL Strategy
- Homepage at `/` follows web conventions
- Edit interface at `/awt` preserves existing bookmarks/links
- Browse functionality at `/browse` provides comprehensive discovery
- Clear hierarchy: discover (/) → browse (/browse) → analyze (/awt) → results (/id/<id>)

### Testing Requirements
- Verify `/` loads correctly with featured elections
- Verify `/awt` form submission still works
- Verify existing `/awt` bookmarks redirect appropriately
- Test navigation flow: homepage → browse → upload → results
- Verify no broken internal links

## Risk Assessment

### Low Risk (0.33)
- Adding new `/` route with minimal template
- Existing `/awt` functionality unchanged
- Template reuse for featured elections
- Basic navigation updates

### Medium Risk (Future)
- Major template restructuring
- Dynamic content generation
- Search functionality implementation
- Mobile responsive design

### Mitigation Strategy
- Implement 0.33 changes incrementally
- Test each route independently
- Preserve all existing query parameters and functionality
- Document any URL changes for users

## Success Metrics

### 0.33 Release
- Homepage loads in <1 second
- Clear user flow from discovery to analysis
- No broken links or missing functionality
- Positive user feedback on separation of concerns

### Future Releases
- Increased election discovery via browse patterns
- Higher conversion from browsing to uploading
- Reduced user confusion about AWT's purpose
- Better search engine visibility and ranking