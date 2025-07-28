# Vision for bifhub

## Overview

**bifhub** is envisioned as a dedicated component responsible for the discovery, cataloging, and management of ABIF (`.abif`) election data files. It will serve as a centralized "ballot box" or registry, providing a stable and queryable interface for other tools in the ecosystem, most notably `awt` (the web frontend) and `abiflib` (the core tallying library).

The primary goal of bifhub is to decouple the logic of *finding* and *managing* election data from the logic of *analyzing* and *displaying* it.

## Core Responsibilities

bifhub will consolidate and replace the functionality currently spread across two different components:

1.  **`fetchmgr.py` (from `abiftool`)**: bifhub will inherit the responsibility for fetching, downloading, and caching remote `.abif` files.
2.  **`abif_list.yml` handling (from `awt`)**: bifhub will manage the metadata, tags, and local file paths currently defined in `abif_list.yml`.

Its core features will include:

*   **Unified Catalog**: Providing a single source of truth for all known elections, whether local or remote.
*   **Metadata Management**: Storing and serving metadata associated with each election (e.g., name, date, jurisdiction, tags).
*   **Queryable Interface**: Allowing client applications like `awt` to query for elections based on tags, IDs, or other metadata.
*   **Local Caching**: Intelligently caching remote files to ensure fast and reliable access.

## Architectural Role

bifhub will sit between the raw data sources (web servers, local files) and the applications that consume that data.

```
+-----------------+      +----------------+      +-----------------+
|  Remote .abif   |      |                |      |                 |
|      files      +------>      bifhub      <------>       awt       |
+-----------------+      |                |      |  (Web Frontend) |
                       | (The Catalog)  |      +-----------------+
+-----------------+      |                |
|   Local .abif   |      |                |      +-----------------+
|      files      +------>                <------>     abiflib     |
+-----------------+      +----------------+      | (Tally Library) |
                                                 +-----------------+
```

By creating this clear separation, `awt` can focus entirely on being a web frontend, and `abiflib` can focus on pure tallying logic, while bifhub handles the data logistics.
