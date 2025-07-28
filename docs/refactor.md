# Refactoring Roadmap for `awt.py`

This document outlines a proposed roadmap for refactoring the `awt.py` monolith into a more modular, maintainable, and scalable structure. The guiding principle is to separate concerns, moving core logic into a dedicated library and leaving `awt.py` as a thin web layer.

## Guiding Principles

1.  **Separation of Concerns**: The primary goal is to isolate different kinds of logic:
    *   **Web Layer**: Code that handles HTTP requests, routes, and web responses (Flask-specific).
    *   **Presentation Logic**: Code that formats data specifically for HTML display.
    *   **Business/Core Logic**: Code that performs the fundamental tasks of the application, like tallying votes or managing data catalogs. This logic should be independent of the web.
2.  **Single Responsibility**: Each new module should have a single, well-defined purpose.
3.  **Incremental Changes**: The refactoring can be done in stages to minimize disruption.

## Proposed Future Structure

The vision is to eventually have a `src/` directory containing the core library, which `awt.py` will use.

```
awt/
├── awt.py            # (Becomes a thin web layer)
├── conduits.py       # (Moves into the library)
├── docs/
│   ├── bifhub.md
│   └── refactor.md   # (This file)
├── src/
│   ├── __init__.py
│   ├── core.py         # (Or conduits.py, for core orchestration)
│   ├── abif_util.py    # (Or bifhub.py, for catalog management)
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

### To `src/abif_util.py` (or `bifhub.py`)

These functions manage the catalog of election files, a responsibility that will ultimately belong to the **bifhub** component.

*   `abif_catalog_init`
*   `build_election_list`
*   `get_fileentry_from_election_list`
*   `get_fileentries_by_tag`
*   `get_all_tags_in_election_list`

### To `src/server_util.py` (Server Utilities)

This module will contain helper functions related to running the web server itself, not the application logic.

*   `find_free_port`

### Remaining in `awt.py` (The Web Layer)

These functions are directly tied to the Flask application, defining routes and handling web requests/responses.

*   `homepage`
*   `awt_get`
*   `id_no_identifier`
*   `get_svg_dotdiagram`
*   `get_by_id`
*   `awt_post`
*   `main` (The application entry point)

By following this plan, `awt.py` will evolve into a clean, dedicated web interface, while the core logic becomes a well-organized and reusable library.
