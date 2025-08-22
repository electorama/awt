# Notices System Design Documentation

## Overview

The AWT/abiftool notice system provides standardized messaging to users about data conversions, edge cases, and methodological caveats across different voting methods. This document describes the current implementation and proposes improvements for a more centralized approach.

## Current Implementation (August 2025)

### Current Architecture: Balkanized by Voting Method

The notice system is currently implemented separately within each voting method module, following a common pattern but without centralized coordination:

#### Pattern Used Across Methods:
```python
# Each voting method returns structured results
{
    "method_specific_data": {...},
    "notices": [
        {
            "notice_type": "note",
            "short": "Brief explanation",
            "long": "Detailed methodology explanation"
        }
    ]
}
```

#### Currently Implemented Methods:

**1. STAR Voting** (`abiflib/score_star_tally.py`):
- **Trigger**: When `is_ranking_to_rating` metadata is present
- **Notice**: Explains Borda scoring conversion from ranked to rated ballots
- **Integration**: Both CLI (`-t text`, `-t json`) and web interface

**2. Approval Voting** (`abiflib/approval_tally.py`):
- **Trigger**: When converting from other ballot types using `favorite_viable_half` algorithm
- **Notice**: Explains strategic simulation methodology
- **Integration**: Both CLI and web interface

**3. Pairwise/Condorcet** (`abiflib/pairwise_tally.py`):
- **Trigger**: When ties or Condorcet cycles are detected
- **Notice**: Explains positioning issues in victory/loss displays
- **Integration**: CLI with `-m notices` modifier, web interface always shows

### Template Integration

**Web Interface**: `templates/notice-snippet.html`
```html
{% if notices %}
{% for notice in notices %}
<div class="notice-banner notice-{{ notice.notice_type }}">
  <div class="notice-icon">📝</div>
  <div class="notice-content">
    <div class="notice-text"><b>Note</b> — {{ notice.short }}</div>
    {% if notice.long %}
    <details>
      <summary>Details</summary>
      <div>{{ notice.long }}</div>
    </details>
    {% endif %}
  </div>
</div>
{% endfor %}
{% endif %}
```

**CLI Integration**: `abiflib/text_output.py`
```python
def format_notices_for_text_output(notices):
    retval = ""
    for notice in notices:
        retval += f"\n[{notice['notice_type'].upper()}] {notice['short']}\n\n"
        retval += textwrap.fill(notice['long'], width=72) + "\n"
    return retval
```

### Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   ABIF Input    │───▶│  Voting Method   │───▶│ Structured      │
│                 │    │  (e.g., STAR)    │    │ Result + Notices│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                       ┌─────────────────────────────────┼─────────────────────────────────┐
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐                ┌──────────────┐                ┌─────────────────┐
              │ CLI Output      │                │ Web Templates│                │ JSON API        │
              │ (text format)   │                │ (HTML)       │                │ (structured)    │
              └─────────────────┘                └──────────────┘                └─────────────────┘
```

## Problems with Current Implementation

### 1. **Balkanization**: Each Method Implements Separately
- **Code Duplication**: Notice structure repeated across modules
- **Inconsistent Triggers**: Different methods use different detection logic
- **Maintenance Burden**: Changes require updates across multiple files
- **Testing Complexity**: Each method needs separate notice testing

### 2. **Inconsistent Integration**
- **CLI**: Some methods always show notices, others require `-m notices` modifier
- **Web**: Some notices always appear, others are conditional
- **JSON**: Notice availability varies by method and output format

### 3. **Limited Extensibility**
- **Cross-Method Notices**: No way to generate notices spanning multiple methods
- **Context-Aware Messages**: Can't adjust notices based on overall election context
- **Notice Prioritization**: No system for ranking notice importance
- **Notice Grouping**: Related notices can't be bundled or deduplicated

### 4. **Metadata Coupling**
- **Tight Binding**: Notice logic embedded within calculation functions
- **Difficult Testing**: Hard to test notice generation independently
- **Inflexible Triggers**: Notice conditions hardcoded in method implementations

## Proposed Centralized Design

### Core Architecture: Notice Registry System

```python
# New centralized notice system
class NoticeRegistry:
    """Central registry for all election analysis notices."""
    
    def __init__(self):
        self.detectors = []  # List of NoticeDetector instances
        self.generated_notices = []
    
    def register_detector(self, detector):
        """Register a notice detector for specific conditions."""
        self.detectors.append(detector)
    
    def analyze_election(self, abifmodel, method_results):
        """Analyze election data and generate relevant notices."""
        self.generated_notices = []
        context = ElectionContext(abifmodel, method_results)
        
        for detector in self.detectors:
            if detector.should_trigger(context):
                notice = detector.generate_notice(context)
                self.generated_notices.append(notice)
        
        return self.generated_notices
```

### Notice Detector Pattern

```python
class NoticeDetector:
    """Base class for notice detection logic."""
    
    def should_trigger(self, context):
        """Return True if this notice should be generated."""
        raise NotImplementedError
    
    def generate_notice(self, context):
        """Generate the notice for this condition."""
        raise NotImplementedError

class BordaConversionDetector(NoticeDetector):
    """Detects when STAR uses Borda conversion from ranked ballots."""
    
    def should_trigger(self, context):
        return (context.has_method_result('star') and 
                context.abifmodel.get('metadata', {}).get('is_ranking_to_rating'))
    
    def generate_notice(self, context):
        return Notice(
            notice_type="conversion",
            scope=["star"],
            short="STAR ratings estimated from ranked ballots using Borda scoring",
            long=self._generate_borda_explanation(context)
        )

class CondorcetCycleDetector(NoticeDetector):
    """Detects Condorcet cycles and pairwise display issues."""
    
    def should_trigger(self, context):
        return (context.has_method_result('pairwise') and 
                context.get_method_result('pairwise').get('has_ties_or_cycles'))
    
    def generate_notice(self, context):
        return Notice(
            notice_type="methodology",
            scope=["pairwise", "condorcet"],
            short="Condorcet cycle or Copeland tie",
            long="\"Victories\" and \"losses\" sometimes aren't displayed..."
        )
```

### Enhanced Notice Structure

```python
@dataclass
class Notice:
    """Enhanced notice with metadata for better management."""
    notice_type: str       # "conversion", "methodology", "data_quality", "warning"
    scope: List[str]       # Affected methods: ["star", "pairwise"]
    short: str             # Brief explanation
    long: str              # Detailed explanation
    priority: int = 1      # 1=high, 2=medium, 3=low
    context_data: dict = field(default_factory=dict)  # Additional context
    
    def applies_to_method(self, method_name):
        """Check if notice applies to specific voting method."""
        return method_name in self.scope or "all" in self.scope
```

### Proposed Integration Points

#### 1. **Centralized Analysis Phase**
```python
def analyze_election_with_notices(abifmodel, requested_methods):
    """Single entry point that generates results and notices together."""
    
    # Calculate all requested voting method results
    method_results = {}
    for method in requested_methods:
        method_results[method] = calculate_method_result(method, abifmodel)
    
    # Generate notices based on complete election context
    notice_registry = get_global_notice_registry()
    notices = notice_registry.analyze_election(abifmodel, method_results)
    
    return ElectionAnalysis(
        abifmodel=abifmodel,
        method_results=method_results,
        notices=notices
    )
```

#### 2. **CLI Integration**
```python
# Enhanced CLI with centralized notice control
parser.add_argument('--notices', choices=['none', 'auto', 'all'], 
                   default='auto',
                   help='Notice display level')

# In output generation:
if args.notices != 'none':
    analysis = analyze_election_with_notices(abifmodel, requested_methods)
    notices = filter_notices_by_level(analysis.notices, args.notices)
else:
    # Legacy mode - no notices
    method_results = calculate_individual_methods(abifmodel, requested_methods)
```

#### 3. **Web Interface Integration**
```python
# In conduits.py - single notice generation point
def update_all_results(self, jabmod):
    """Generate all results and notices together."""
    
    # Calculate all method results
    methods = ['fptp', 'irv', 'pairwise', 'star', 'approval']
    for method in methods:
        getattr(self, f'update_{method}_result')(jabmod)
    
    # Generate notices based on complete context
    analysis = analyze_election_with_notices(jabmod, methods)
    self.resblob['notices'] = group_notices_by_scope(analysis.notices)
```

### Benefits of Centralized Design

#### 1. **Cross-Method Intelligence**
- **Global Context**: Notices can consider interactions between voting methods
- **Conflict Detection**: Identify when methods give contradictory results
- **Comprehensive Analysis**: Single notice can explain impacts across multiple methods

#### 2. **Consistent User Experience**
- **Unified Triggers**: Same conditions generate notices across CLI and web
- **Consistent Formatting**: Single codebase for notice presentation
- **Predictable Behavior**: Users get same notices regardless of interface

#### 3. **Enhanced Maintainability**
- **Single Source of Truth**: All notice logic in one place
- **Easy Testing**: Notice generation can be tested independently
- **Simple Extensions**: Adding new notices requires minimal code changes

#### 4. **Advanced Features**
- **Notice Prioritization**: Show most important notices first
- **Context-Sensitive Help**: Tailor explanations to specific election characteristics
- **Notice Grouping**: Combine related notices to reduce clutter
- **Progressive Disclosure**: Brief notices with expandable details

## Migration Strategy

### Phase 1: Establish Infrastructure (Low Risk)
1. Create `NoticeRegistry` and `NoticeDetector` base classes
2. Implement `format_notices_for_text_output()` enhancements
3. Add centralized notice filtering and grouping utilities
4. Create comprehensive test suite for notice system

### Phase 2: Migrate Existing Notices (Medium Risk)
1. Convert STAR Borda conversion notice to detector pattern
2. Convert approval conversion notice to detector pattern  
3. Convert pairwise cycle notice to detector pattern
4. Maintain backward compatibility during transition

### Phase 3: Enhanced Integration (High Risk)
1. Implement centralized `analyze_election_with_notices()`
2. Update CLI to use centralized system
3. Update web interface (conduits.py) to use centralized system
4. Add advanced features (prioritization, grouping, etc.)

### Phase 4: Advanced Features (Future)
1. Cross-method notices (e.g., "IRV and Condorcet disagree")
2. Data quality notices (e.g., "High abstention rate detected")
3. Contextual help system
4. Notice customization and user preferences

## Implementation Notes

### Backward Compatibility
- Existing notice structures should remain supported
- CLI behavior should not change unless explicitly requested
- Web interface notices should not disappear or change formatting

### Performance Considerations
- Notice detection should be lightweight and fast
- Notice generation should be lazy (only when needed)
- Complex analysis should be cached between method calculations

### Testing Strategy
- Unit tests for each notice detector
- Integration tests for complete notice generation
- UI tests for notice display in both CLI and web
- Regression tests to ensure existing notices continue working

### Configuration
- Notice detectors should be configurable/pluggable
- Users should be able to disable specific notice types
- Administrators should be able to customize notice text

## Conclusion

The current balkanized notice system works but creates maintenance burden and limits extensibility. A centralized design would provide better user experience, easier maintenance, and enable advanced features like cross-method analysis and notice prioritization.

The proposed migration strategy allows for gradual implementation while maintaining backward compatibility, making it a low-risk improvement with significant long-term benefits.

## Current Implementation Challenges (August 2025 Update)

### Real-World Experience: The Route Duplication Problem

Recent development work revealed a significant architectural issue with the balkanized notice system: **route duplication**. When adding pairwise tie notices, the implementation had to be duplicated across different request handling paths:

#### The Problem
- **GET requests** (e.g., `/id/TNexampleTie`): Process pairwise data directly in `awt.py` main route
- **POST requests** (e.g., form submissions): Process pairwise data through `conduits.py` pipeline
- **Result**: Same notice generation logic had to be implemented in **both places**

#### Code Locations of Duplicated Logic
```python
# Location 1: conduits.py (for POST route)
def update_pairwise_result(self, jabmod):
    # ... pairwise processing ...
    if self.resblob['is_copeland_tie'] and len(copewinners) >= 2:
        # Generate Copeland tie notice
        copeland_notice = {...}
        self.resblob['notices']['pairwise'].append(copeland_notice)

# Location 2: awt.py (for GET route) - DUPLICATE LOGIC
def get_by_id(this_id, resulttype=None):
    # ... pairwise processing ...
    if resblob['is_copeland_tie'] and len(copewinners) >= 2:
        # Generate Copeland tie notice - SAME CODE, DIFFERENT LOCATION
        copeland_notice = {...}
        resblob['notices']['pairwise'].append(copeland_notice)
```

### Lessons for Future Notice Development

#### 1. **Expect Route Duplication**
Adding notices to the current system is **not** straightforward. Developers must implement the same logic in multiple places:
- `conduits.py` for form-based POST requests
- `awt.py` for direct GET requests
- Potentially other routes for API endpoints

#### 2. **Template Integration Gotchas**
- Notice extraction happens via `_extract_notices()` method calls
- **Timing matters**: Multiple `_extract_notices()` calls can override each other
- Debug with `fetch_awt_url.py`, not just template inspection
- Notice structure must exist before extraction: `resblob['notices']['method'] = []`

#### 3. **Testing Complexity**
- Same notice must work across multiple request types (GET/POST)
- Template rendering can differ between routes
- Need to test both `/id/election` and form submissions
- PEP8 compliance failures are common (trailing whitespace)

### Recommendations for Legacy System Development

#### For Developers Adding New Notices

**Before implementing:**
1. **Read this document first** - understand the architectural challenges
2. **Identify all code paths** - trace GET routes, POST routes, and API endpoints
3. **Plan for duplication** - expect to implement logic in multiple places
4. **Test comprehensively** - verify notices work across all request types

#### For Improving the Legacy System

**Short-term improvements that would help developers:**

1. **Create Notice Helper Functions**
   ```python
   # In a shared utility module
   def generate_copeland_tie_notice(copewinners, jabmod):
       """Shared logic for Copeland tie notices across routes."""
       # Single implementation used by both conduits.py and awt.py
   ```

2. **Standardize Notice Injection Points**
   ```python
   # Add to conduits.py
   def inject_notices_for_method(self, method_name, notices):
       """Standardized way to add notices to resblob."""
       if 'notices' not in self.resblob:
           self.resblob['notices'] = {}
       if method_name not in self.resblob['notices']:
           self.resblob['notices'][method_name] = []
       self.resblob['notices'][method_name].extend(notices)
   ```

3. **Route Processing Consolidation**
   - Consider making GET routes use `conduits.py` pipeline consistently
   - Or create shared processing functions that both routes can use
   - Avoid duplicating calculation and notice logic across routes

4. **Debug Utilities**
   ```python
   # Debug helper for notice development
   def debug_notice_pipeline(resblob, method_name):
       """Print notice pipeline state for debugging."""
       notices = resblob.get('notices', {}).get(method_name, [])
       print(f"DEBUG: {method_name} has {len(notices)} notices")
       for i, notice in enumerate(notices):
           print(f"  Notice {i+1}: {notice.get('short', 'No short text')}")
   ```

#### Current Technical Debt from Notice Development

**Items that need refactoring:**
- **Duplicate Copeland tie detection**: Same logic in `conduits.py:274-296` and `awt.py:1004-1021`
- **Inconsistent notice extraction**: Some methods use `_extract_notices()`, others manually build `resblob['notices']`
- **Route-dependent behavior**: Same election shows different notices depending on GET vs POST access
- **Template debugging complexity**: Notice positioning issues require end-to-end testing with `fetch_awt_url.py`

**Priority for centralized system:**
The route duplication problem makes a strong case for the proposed centralized `NoticeRegistry` system. A single analysis phase would eliminate the need to implement notices in multiple request handling paths.