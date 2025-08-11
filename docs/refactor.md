# Refactoring Roadmap for `awt.py`

This document outlines a proposed roadmap for refactoring the `awt.py` monolith into a more modular, maintainable, and scalable structure. The guiding principle is to separate concerns, moving core logic into a dedicated library and leaving `awt.py` as a thin web layer.

## Guiding Principles

1.  **Separation of Concerns**: The primary goal is to isolate different kinds of logic:
    *   **Web Layer**: Code that handles HTTP requests, routes, and web responses (Flask-specific).
    *   **Data Transformation Layer**: Code that adapts between abiflib output and web-friendly structures (`conduits.py`).
    *   **Presentation Logic**: Code that formats data specifically for HTML display.
    *   **Catalog Management**: Code that manages election file discovery and metadata (future bifhub service).
2.  **Single Responsibility**: Each new module should have a single, well-defined purpose.
3.  **Incremental Changes**: The refactoring can be done in stages to minimize disruption.
4.  **Thin Web Layer**: `awt.py` should become a minimal Flask application with nearly all logic moved to `src/`.

## Proposed Future Structure

The vision is to eventually have a `src/` directory containing the core library, which `awt.py` will use.

```
awt/
├── awt.py            # (Becomes a thin web layer)
├── docs/
│   ├── bifhub.md
│   └── refactor.md   # (This file)
├── src/
│   ├── __init__.py
│   ├── conduits.py     # (Data transformation layer: abiflib → web-friendly structures)
│   ├── bifhub.py       # (Catalog management - future separate service)
│   ├── html_util.py    # (For presentation logic)
│   └── server_util.py  # (For server-related helpers)
├── static/
└── templates/
```

## Function Migration Plan

Here is a breakdown of the functions currently in `awt.py` and their proposed new homes within the `src/` library.

### To `src/html_util.py` (Presentation Logic)

These functions are responsible for generating HTML snippets or preparing data structures for Jinja templates.

*   `jinja_pairwise_snippet`
*   `jinja_scorestar_snippet`
*   `generate_golden_angle_palette` (The color generator)
*   `add_html_hints_to_stardict`

### To `src/bifhub.py` (Catalog Management)

These functions manage the catalog of election files. This module is designed to eventually become a separate bifhub service/database.

*   `abif_catalog_init`
*   `build_election_list`
*   `get_fileentry_from_election_list`
*   `get_fileentries_by_tag`
*   `get_all_tags_in_election_list`

### To `src/server_util.py` (Server Utilities)

This module will contain helper functions related to running the web server itself, not the application logic.

*   `find_free_port`

### To `src/conduits.py` (Data Transformation Layer)

This module serves as the adapter between abiflib's raw election analysis and web-friendly data structures for Flask/Jinja templates.

*   `ResultConduit` class and all its methods
*   Notice consolidation and `resblob` construction logic

### Remaining in `awt.py` (The Web Layer)

These functions are directly tied to the Flask application, defining routes and handling web requests/responses.

*   `homepage`
*   `awt_get`
*   `id_no_identifier`
*   `get_svg_dotdiagram`
*   `get_by_id`
*   `awt_post`
*   `main` (The application entry point)

## Migration Order (Recommended)

The refactoring should proceed incrementally to minimize risk and allow testing at each step:

1.  **src/html_util.py** - Pure presentation functions with no dependencies (lowest risk)
2.  **src/server_util.py** - Simple utilities with minimal coupling
3.  **src/bifhub.py** - Catalog management functions (prepares for future service split)
4.  **src/conduits.py** - Data transformation layer (requires coordination with template updates)

Each step should be fully tested before proceeding to the next, ensuring `awt.py` remains functional throughout the process.

## Benefits

By following this plan, `awt.py` will evolve into a clean, dedicated web interface, while the core logic becomes a well-organized and reusable library. The modular structure also prepares for the eventual split of bifhub into a separate service for catalog management.
