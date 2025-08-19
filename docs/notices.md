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