# AWT Routes Documentation

This document describes the current URL routes (endpoints) available in the ABIF Web Tool (AWT).

## Current Top-Level Routes

### `/`
- **Method**: GET
- **Purpose**: Root homepage
- **Description**: Entry point for discovery and navigation (introduced in 0.33)

### `/awt`
- **Methods**: GET, POST
- **Purpose**: Main homepage and ABIF processing endpoint
- **GET**: Displays the homepage with ABIF input form, voting method checkboxes, and tabbed examples
- **POST**: Processes submitted ABIF data and returns election results
- **Features**:
  - Large textarea for ABIF input
  - Checkboxes for enabling different voting methods (FPTP, IRV, STAR, Approval, Condorcet)
  - Tabbed examples section with 5 featured elections
  - "Other examples..." tab showing additional elections

### `/browse`
- **Method**: GET
- **Purpose**: Enhanced election discovery interface (introduced in 0.33)
- **Description**: Organized, searchable interface for browsing elections with filtering capabilities
- **Features**: Improved UX compared to raw `/id` listing

### `/edit`
- **Method**: GET
- **Purpose**: Election editing interface (future feature)
- **Description**: Redirects to `/awt` (as of 0.33); planned to become primary upload/analysis interface in a later release
- **Status**: Redirect to `/awt` (introduced in 0.33)

### `/id`
- **Method**: GET
- **Purpose**: Lists all available elections (currently 425 elections)
- **Description**: Shows a comprehensive but unsorted list of all elections in the system
- **Format**: Numbered list with election identifiers, descriptions, and tag links
- **Issues**: Large list is difficult to navigate and discover specific elections

### `/tag`
- **Method**: GET
- **Purpose**: Shows list of available tags
- **Description**: Displays all available tags for filtering elections

### `/tag/<tag>`
- **Method**: GET
- **Purpose**: Shows elections filtered by a specific tag
- **Examples**: `/tag/actual`, `/tag/theoretical`, `/tag/USA`, `/tag/VT`, `/tag/CondorcetVsIRV`
- **Description**: Filters the election list to show only elections with the specified tag

## Dynamic Election Routes

### `/id/<identifier>`
- **Method**: GET
- **Purpose**: Shows complete election results for a specific election
- **Examples**: `/id/Burl2009`, `/id/TNexample`, `/id/sf2024-mayor`
- **Features**: Displays results for all enabled voting methods with tabbed interface

### `/id/<identifier>/<resulttype>`
- **Method**: GET  
- **Purpose**: Shows specific result type for an election
- **Examples**: `/id/Burl2009/pairwise`, `/id/Burl2009/IRV`, `/id/Burl2009/STAR`
- **Supported resulttypes**: `pairwise`, `IRV`, `FPTP`, `STAR`, `approval`, `dot`, `wlt`
- **Note**: `pairwise` resulttype maps to both `dot` and `wlt` internally

### `/id/<identifier>/dot/svg`
- **Method**: GET
- **Purpose**: Returns SVG diagram for pairwise (Condorcet) results
- **Content-Type**: image/svg+xml
- **Description**: Generates Graphviz-based pairwise comparison diagrams

## Deprecated Routes (since 0.33)

### `/id/<identifier>/dot` (Deprecated)
- **Method**: GET
- **Purpose**: Legacy route for pairwise diagrams
- **Status**: Redirects to `/id/<identifier>/pairwise#dot` (HTTP 302)
- **Migration**: Use `/id/<identifier>/pairwise` instead

### `/id/<identifier>/wlt` (Deprecated)
- **Method**: GET
- **Purpose**: Legacy route for win-loss-tie tables
- **Status**: Redirects to `/id/<identifier>/pairwise#wlt` (HTTP 302)
- **Migration**: Use `/id/<identifier>/pairwise` instead

## Static Asset Routes

### `/static/<path>`
- **Purpose**: Serves static files (CSS, JavaScript, images)
- **Examples**: `/static/css/electostyle.css`, `/static/js/abifwebtool.js`, `/static/img/awt-electorama.svg`

## Catch-All Route

### `/<toppage>`
- **Method**: GET
- **Purpose**: Handles other GET requests not matched by specific routes
- **Description**: Fallback route for general page requests

## Route Hierarchy

```
/                           # Root homepage
├── awt                     # Homepage/main app
├── browse                  # Enhanced election discovery
├── edit                    # Election editing (future)
├── id                      # Election listing
│   └── <identifier>        # Individual election
│       ├── <resulttype>    # Specific results
│       └── dot/svg         # SVG diagrams
├── tag                     # Tag listing
│   └── <tag>               # Tag-filtered elections
├── static/<path>           # Assets
└── <toppage>               # Catch-all
```

## Notes

- Most user interaction flows through `/awt` (edit/upload) and `/id/<identifier>` (election results)
- The `/id` route serves as a discovery mechanism but has usability challenges due to the large number of elections
- Tag-based filtering via `/tag/<tag>` provides some organization but is not prominently featured
- Route naming follows a pattern where `/id` is for browsing elections and `/id/<identifier>` is for viewing specific election results
