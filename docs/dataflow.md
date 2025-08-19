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

### 4. **conduits.py as Bottleneck**
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

## Release-Based Roadmap for Data Flow Improvements

### Release 0.33: Stability and Foundation

**Goals**: Complete existing pattern standardization, fix critical bugs, prepare stable foundation for 0.34.

#### Core Infrastructure Tasks:
- **Complete IRV CLI Transition** 
  - Update `get_IRV_report()` to use `IRV_result` structure
  - Ensure CLI and web consistency for IRV results
  - Document function naming relationships (`*_dict_from_jabmod()` vs `*_result_from_abifmodel()`)

- **Bug Fixes and Stability**
  - Address critical issues blocking 0.33 release
  - Ensure color consistency across existing functionality
  - Fix any template regressions or display issues

- **Documentation for 0.34 Planning**
  - Document current notice infrastructure limitations (fragmented `_extract_notices`, abiflib/awt coupling issues)
  - Identify cross-cutting concerns that need architectural work (candidate colors, notice infrastructure)
  - Assess what infrastructure improvements are needed before template simplification

#### Expected Outcomes:
- Stable, working codebase ready for release
- All voting methods follow consistent implementation patterns
- Clear documentation of architectural issues to address in 0.34
- Foundation ready for cross-cutting concerns work

### Release 0.34: Cross-Cutting Concerns and Scaling

**Goals**: Establish cross-cutting concerns patterns, support many more elections, begin candidate color system standardization.

#### Cross-Cutting Concerns Infrastructure:
- **Notice Infrastructure Redesign**
  - Redesign notice passing between abiflib and awt (eliminate fragmented `_extract_notices` pattern)
  - Create cleaner abiflib notice infrastructure that awt can consume directly
  - Establish notice system as foundation pattern for other cross-cutting concerns

- **Candidate Color System Standardization**
  - Investigate and document candidate token mapping across voting methods
  - Centralize color assignment logic in conduits.py 
  - Ensure consistent candidate colors across summary tables, detailed results, and tabs
  - Create automated tests for color consistency

- **Template Data Standardization**
  - Apply proven cross-cutting patterns to NEW features first
  - Build helper method library based on successful notice infrastructure
  - Establish guidelines for when to use Python vs template logic

#### Import Pipeline Enhancements:
- **Unified Format Converter Interface**
  - Standardize metadata setting across all converters (sftxt, preflib, nycdem)
  - Automatic `ballot_type` detection and validation
  - Consistent conversion notice generation

- **Enhanced Metadata System**
  - Improve abiflib metadata processing for large elections
  - Better memory usage for bulk election processing
  - Validation pipeline for imported election data

#### Expected Outcomes:
- Candidate color consistency across all voting method displays
- Proven patterns for cross-cutting concerns using ResultConduit
- Capacity for 10x more elections without performance degradation  
- Streamlined import process for new election sources
- Clear guidelines for template vs Python logic decisions

### Release 0.35: Template Simplification and Advanced Cross-Method Analysis

**Goals**: Apply proven cross-cutting patterns to template simplification, intelligent notice aggregation, enhanced developer experience.

#### Template Simplification (Based on 0.34 Patterns):
- **Selective Template Logic Replacement**
  - Start with simplest cross-cutting concerns after color system is stable
  - Replace template calculations using proven ResultConduit patterns
  - Incremental replacement with thorough testing (one voting method at a time)
  - Maintain strict "no regressions" policy

- **Enhanced Template Helper Library**
  - Build on successful 0.34 helper method patterns
  - Create reusable components for common template operations
  - Standardize template data structures across voting methods

#### Advanced Notice System:
- **Cross-Method Intelligence**
  - Cross-method notice generation (e.g., "IRV and Condorcet disagree")
  - Context-sensitive notice text based on ballot type and election characteristics
  - Notice prioritization and smart grouping to reduce information overload

- **Enhanced Import Validation**
  - Data quality warnings and validation notices
  - Standardized conversion notices across all format converters
  - Import pipeline notices for debugging election data issues

#### Expected Outcomes:
- Proven template simplification approach based on stable cross-cutting infrastructure
- Intelligent notice system that provides insights across voting methods
- Better user education about election methodology trade-offs
- Enhanced debugging capabilities for election imports
- Maintainable template architecture with clear Python vs Jinja2 boundaries

### Release 0.36: Architectural Completion and Optimization

**Goals**: Complete bifhub separation, performance optimization, stable external APIs.

#### bifhub Service Separation:
- **Complete Service Extraction**
  - Separate bifhub as standalone service
  - API for election discovery and metadata management
  - Database backend for election catalog

- **Performance Optimization**
  - Lazy loading for large election datasets
  - Caching strategies for frequently accessed elections
  - Memory usage optimization for bulk processing

#### API Stabilization:
- **External API Compatibility**
  - Stable JSON API for third-party integrations
  - Versioned data structures
  - Comprehensive API documentation

- **Developer Experience**
  - Clear patterns for adding new voting methods
  - Comprehensive testing framework
  - Migration guides for API changes

#### Expected Outcomes:
- Fully separated, scalable architecture
- Stable APIs for external integrations
- Optimized performance for large-scale election analysis
- Clear patterns for future development

## Proposed Enhanced Notice System (0.35 Target)

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
    notice_type: str       # "conversion", "methodology", "disagreement"
    scope: List[str]       # Affected methods: ["star", "pairwise"]
    short: str             # Brief explanation
    long: str              # Detailed explanation  
    priority: int = 1      # 1=high, 2=medium, 3=low
    context_data: dict = field(default_factory=dict)
```

## Migration and Compatibility Strategy

### Backward Compatibility Guarantees:
- **0.33**: Existing APIs remain functional, enhanced with new patterns
- **0.34**: Legacy `*_dict_from_jabmod()` functions maintained during transition
- **0.35**: Clear migration path for notice system changes
- **0.36**: Deprecated APIs removed with comprehensive migration guide

### Risk Management:
- **Incremental Changes**: Each release builds on previous foundation
- **Feature Flags**: New functionality can be enabled/disabled during transition
- **Regression Testing**: Comprehensive test suite for existing election results
- **Documentation**: Clear upgrade guides for each release

### Performance Considerations:
- **0.33**: Optimize existing patterns before adding complexity
- **0.34**: Design import pipeline for large-scale datasets
- **0.35**: Intelligent caching for notice generation
- **0.36**: Full performance optimization and profiling

## Success Metrics by Release

### 0.33 Success Criteria:
- All voting methods use consistent `*_result_from_abifmodel()` pattern
- Templates contain no arithmetic calculations  
- CLI and web outputs are identical for same inputs
- Function naming clarity (`*_dict_from_jabmod()` vs `*_result_from_abifmodel()` relationship documented)
- Critical bugs fixed, stable release ready

### 0.34 Success Criteria:  
- Support for 10x more elections without performance degradation
- New election import process streamlined (fewer manual steps)
- Bifhub foundation established (catalog separation begun)
- Tech debt metrics improved (code duplication reduced)

### 0.35 Success Criteria:
- Cross-method notices provide valuable insights to users
- Notice system reduces user confusion about methodology differences
- Developer experience improved (easier to add new voting methods)
- Import pipeline handles edge cases gracefully

### 0.36 Success Criteria:
- bifhub operates as separate, scalable service
- External API usage demonstrates adoption
- Performance metrics meet large-scale usage requirements
- Architecture supports future voting method additions with minimal effort

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

## Immediate Priorities for 0.33

Based on current development focus, the recommended next tasks are:

1. **Bug Fixes** - Address critical issues blocking 0.33 release
2. **Complete IRV CLI Transition** - Update `get_IRV_report()` to use `IRV_result` structure  
3. **Function Naming Documentation** - Clarify `*_dict_from_jabmod()` vs `*_result_from_abifmodel()` usage
4. **Architecture Documentation** - Document notice infrastructure limitations and cross-cutting concerns for 0.34 planning

**Notice infrastructure redesign is deferred to 0.34** to allow focus on stability and bug fixes for 0.33 release.

## Conclusion

This release-based roadmap addresses the core problems constraining scaling and import pipeline improvements while maintaining the architectural vision of conduits.py as an intelligent data broker. The approach emphasizes **pragmatic shared infrastructure** over complex hierarchies, focusing on eliminating duplication while keeping structures flat and maintainable.

Each release builds systematically toward supporting many more elections with easier import processes, with 0.33 establishing the foundation, 0.34 focusing on scaling and imports, 0.35 adding intelligent cross-method analysis, and 0.36 completing the bifhub separation and optimization work.