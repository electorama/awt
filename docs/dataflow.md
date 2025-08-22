# Data Flow Architecture Documentation

## Overview

This document describes the current data pipeline between abiflib (the core election analysis library) and awt (the web interface), with focus on achieving consistent developer experience (DX) across all voting methods and scaling to support many more elections. The inconsistent notice system reveals a broader problem: each voting method currently implements its own patterns, creating maintenance burden and confusion.

The goal is to have abiftool/abiflib provide canonical analysis while awt provides web presentation, with conduits.py serving as the intelligent data broker that creates consistent, web-ready structures from abiflib's raw outputs.

## Current State: Inconsistent Patterns Creating DX Problems

### The Notice System Problem (Symptom of Broader Issues)

The notice system reveals the core problem: each voting method implements its own patterns, creating maintenance burden and scaling constraints.

#### Current Notice Implementation (Balkanized by Method):

**STAR Voting** (`abiflib/score_star_tally.py`):
- **Trigger**: `is_ranking_to_rating` metadata present
- **Notice**: Explains Borda scoring conversion from ranked to rated ballots
- **Integration**: Both CLI (`-t text`, `-t json`) and web interface

**Approval Voting** (`abiflib/approval_tally.py`):
- **Trigger**: Converting from other ballot types using `favorite_viable_half`
- **Notice**: Explains strategic simulation methodology
- **Integration**: Both CLI and web interface

**Pairwise/Condorcet** (`abiflib/pairwise_tally.py`):
- **Trigger**: Ties or Condorcet cycles detected
- **Notice**: Explains positioning issues in displays
- **Integration**: CLI with `-m notices` modifier, web interface always shows

**FPTP & IRV**: No notice system yet

### High-Level Data Pipeline
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
│   ABIF Input    │───▶│    abiflib       │───▶│   conduits.py   │───▶│ Templates    │
│ (many formats)  │    │  (calculations)  │    │ (data broker)   │    │ (presentation│
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────┘
                                │                       │                       │
                                ▼                       ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
                       │ abiftool CLI    │    │ Structured      │    │ HTML Output     │
                       │ (text output)   │    │ resblob         │    │ (web interface) │
                       └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Current Method Implementation Patterns

#### **Pattern A: Structured Results** (Preferred, Recently Adopted):
1. **STAR**: `STAR_result_from_abifmodel()` → `conduits.py` → web templates
2. **Approval**: `approval_result_from_abifmodel()` → `conduits.py` → web templates  
3. **Pairwise**: `pairwise_result_from_abifmodel()` → `conduits.py` → web templates
4. **FPTP**: `FPTP_result_from_abifmodel()` → `conduits.py` → web templates
5. **IRV**: `IRV_result_from_abifmodel()` → `conduits.py` → web templates *(newly added)*

#### **Pattern B: Legacy Dict Functions** (Being Phased Out):
- **IRV**: Still uses `IRV_dict_from_jabmod()` alongside new function
- **Templates**: Complex calculations embedded in Jinja2 templates
- **Problem**: Divergence between CLI and web outputs, maintenance burden

#### **Pattern C: Direct Template Logic** (Legacy, Problematic):
- **Some methods**: Raw data passed to templates, calculations done in Jinja2
- **Problem**: Template complexity, no reusability for CLI output

## Problems Constraining Scaling and New Election Import

### 1. **Developer Experience Inconsistency**
- **Different APIs**: Some methods use `*_result_from_abifmodel()`, others use `*_dict_from_jabmod()`
- **Template Complexity**: Some templates do calculations, others just format pre-computed data
- **Notice Fragmentation**: Each method implements notices differently
- **Testing Burden**: Every new election format requires testing each method's unique patterns

### 2. **Import Pipeline Fragmentation**
- **Format Converters**: Each converter (sftxt, preflib, nycdem) sets different metadata patterns
- **Metadata Inconsistency**: `ballot_type` detection varies by source format  
- **Notice Triggers**: Conversion notices generated inconsistently across formats
- **Validation Gaps**: No centralized validation of imported election data

### 3. **Scaling Constraints**
- **Code Duplication**: Notice logic repeated across methods
- **Template Maintenance**: Complex templates hard to debug and modify
- **Testing Complexity**: Each method needs separate notice and display testing
- **Memory Usage**: Inefficient data structures for large election datasets

### 4. **Route Processing Duplication**
- **Dual Processing Paths**: GET requests bypass conduits.py, POST requests use it
- **Duplicate Business Logic**: Same calculations implemented in both `awt.py` and `conduits.py`
- **Notice System Impact**: Requires implementing same notice logic in multiple places
- **Developer Friction**: Adding features requires changes in multiple code paths
- **Testing Complexity**: Same functionality must be verified across different routes

### 5. **conduits.py as Bottleneck**
- **Mixed Patterns**: Some methods bypass conduits, others use it heavily
- **Inconsistent Interface**: No standard pattern for how conduits processes abiflib results
- **Notice Aggregation**: No centralized place for cross-method notice generation
- **Data Structure Variance**: Each method creates different resblob structures

## Current Notice System Architecture (Detailed)

### Template Integration Pattern
```html
<!-- templates/notice-snippet.html -->
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

### CLI Integration Pattern
```python
# abiflib/text_output.py
def format_notices_for_text_output(notices):
    retval = ""
    for notice in notices:
        retval += f"\n[{notice['notice_type'].upper()}] {notice['short']}\n\n"
        retval += textwrap.fill(notice['long'], width=72) + "\n"
    return retval
```

### Current Notice Data Flow
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

## Target Architecture: conduits.py as Intelligent Data Broker

### Design Philosophy: Flatter Structure with Shared Infrastructure

Based on development experience, the target architecture emphasizes **pragmatic shared infrastructure** over complex hierarchical structures. The focus is on eliminating duplication (especially in notices) while keeping the resblob structure flat and maintainable.

#### Proposed Flat resblob Structure:
```python
resblob = {
    # Shared infrastructure (extracted once)
    'notices': [...],              # All notices from all methods
    'election_metadata': {...},    # Ballot type, total ballots, etc.
    'candidate_info': {            # Shared across all methods
        'names': {...},            # Canonical name mapping  
        'colors': {...},           # Color assignments
        'display_order': [...]     # Consistent ordering
    },
    
    # Method results (consistent summary pattern)
    'FPTP_result': {
        'winner': '...', 'runner_up': '...', 'winner_votes': N,
        'method_specific_data': {...}
    },
    'IRV_result': {
        'winner': '...', 'runner_up': '...', 'winner_votes': N, 
        'method_specific_data': {...}
    },
    # All methods follow same summary structure
}
```

### Enhanced Data Flow Vision
```
┌─────────────────┐    ┌──────────────────────────────────────┐    ┌─────────────────┐
│   ABIF Input    │───▶│           abiflib Core              │───▶│ Raw Election    │
│ (many formats)  │    │                                      │    │ Analysis        │
│                 │    │ METHOD_result_from_abifmodel()       │    │                 │
│                 │    │ ├── Calculations                     │    │ ├── method_data │
│                 │    │ ├── Basic summaries                 │    │ ├── summary     │
│                 │    │ └── Method-specific notices         │    │ └── notices     │
└─────────────────┘    └──────────────────────────────────────┘    └─────────────────┘
                                                                            │
                                                                            ▼
                                                          ┌─────────────────────────────┐
                                                          │      conduits.py            │
                                                          │   (Enhanced Data Broker)    │
                                                          │                             │
                                                          │ ├── Aggregate all methods   │
                                                          │ ├── Cross-method notices    │
                                                          │ ├── Consistent formatting   │
                                                          │ ├── Template-ready data     │
                                                          │ └── Performance optimization│
                                                          └─────────────────────────────┘
                                                                            │
                       ┌────────────────────────────────────────────────────┼────────────────────────────────────────────────────┐
                       ▼                                                    ▼                                                    ▼
              ┌─────────────────┐                                  ┌──────────────┐                                  ┌─────────────────┐
              │ abiftool CLI    │                                  │ awt Web UI   │                                  │ JSON API        │
              │                 │                                  │              │                                  │                 │
              │ get_*_report()  │                                  │ Templates    │                                  │ Direct export   │
              │ (from resblob)  │                                  │ (minimal)    │                                  │ of resblob      │
              │                 │                                  │              │                                  │                 │
              └─────────────────┘                                  └──────────────┘                                  └─────────────────┘
```

### Key Architectural Principles

1. **conduits.py as Central Orchestrator**: Takes raw abiflib results and creates consistent, web-ready data
2. **Unified Notice System**: Cross-method notice detection and intelligent aggregation
3. **Consistent APIs**: All methods follow same patterns for easier maintenance and testing
4. **Template Simplification**: Web templates only format, never calculate
5. **CLI/Web Consistency**: Both interfaces use same underlying data structures

## Potential Future Direction

The following sections outline possible future work, but are not a firm roadmap. The focus for the immediate future is on stabilizing the 0.33 release.



### Possible Future Exploration (Post-0.33)

After the 0.33 release, several areas could be explored to improve the system's architecture, scalability, and developer experience. These are ideas for consideration, not committed features.

#### Potential Area: Cross-Cutting Concerns
A significant area for future work could be establishing patterns for handling cross-cutting concerns like notices and candidate color assignments.

- **Notice Infrastructure**: One could redesign how notices are passed between `abiflib` and `awt` to eliminate duplicated logic and create a more centralized system.
- **Candidate Color System**: Another area of exploration could be to centralize the candidate color assignment logic to ensure consistency across all views and methods.
- **Template Data Standardization**: Future work might involve creating a more robust helper library to standardize the data passed to templates, reducing logic in the presentation layer.

#### Potential Area: Import Pipeline
The process of importing new elections could be streamlined.

- **Unified Converters**: The various format converters could be unified under a standard interface for metadata handling.
- **Enhanced Metadata**: The system could be improved to handle metadata from large elections more efficiently.

#### Potential Area: Template Simplification
If the cross-cutting concern patterns prove successful, they could be applied to simplify the Jinja2 templates.

- **Selective Refactoring**: Logic could be moved from templates into Python code, one method at a time.
- **Helper Library**: A library of helper functions could be built out to support the simplified templates.

#### Potential Area: Advanced Analysis and API
Further out, the system could be enhanced with more advanced features.

- **Cross-Method Analysis**: The notice system could be made more intelligent, for example, by detecting when different voting methods produce different winners.
- **bifhub Service**: The `bifhub` component could be separated into a standalone service with its own API.
- **Performance**: Caching and data loading strategies could be improved to support larger-scale analysis.
- **API Stabilization**: A stable, versioned JSON API could be created for third-party integrations.

## Proposed Enhanced Notice System

### Centralized Notice Architecture
```python
# New unified notice system
class NoticeDetector:
    """Base class for notice detection logic"""
    def should_trigger(self, context): ...
    def generate_notice(self, context): ...

class BordaConversionDetector(NoticeDetector):
    """Detects STAR Borda conversion from ranked ballots"""
    def should_trigger(self, context):
        return (context.has_method_result('star') and 
                context.abifmodel.get('metadata', {}).get('is_ranking_to_rating'))

class CrossMethodDisagreementDetector(NoticeDetector):
    """Detects when different methods produce different winners"""
    def should_trigger(self, context):
        winners = {method: result.get('winner') 
                  for method, result in context.method_results.items()}
        return len(set(winners.values())) > 1
```

### Enhanced Notice Structure
```python
@dataclass
class Notice:
    notice_type: str       # "note", "warning", "info", "debug""
    scope: List[str]       # Affected methods: ["star", "pairwise"]
    short: str             # Brief explanation
    long: str              # Detailed explanation  
    priority: int = 1      # 1=high, 2=medium, 3=low
    context_data: dict = field(default_factory=dict)
```


## Current Cross-Cutting Concerns Analysis

### Candidate Color System (Priority Target for 0.34)

The candidate color system represents a fragile cross-cutting concern that affects multiple template sections:

**Current Issues:**
- Different voting methods use different candidate token mappings
- Color consistency breaks when same candidate appears in different contexts
- Template logic complexity around color assignment and candidate name resolution
- No centralized color assignment or validation

**Opportunity for conduits.py Enhancement:**
- Centralize candidate token resolution across all voting methods  
- Standardize color assignment to ensure same candidate = same color everywhere
- Create helper methods for consistent candidate display (name + colorbox)
- Establish automated testing for color consistency

**Template Sections Affected:**
- Winner summary table (cross-method comparison)
- Individual voting method results
- Tab navigation color indicators
- Detailed result displays

This system would be an excellent candidate for the ResultConduit cross-cutting concerns pattern, as it requires coordination across all voting methods and has clear template integration points.

## Conclusion

Data should flow from abiflib into Jinja through conduits.py.  Exactly
how is TBD.