# Storage Engine

The storage layer persists data into a JSON database file while exposing a page-oriented API.

Each table is stored as:

- schema metadata
- a list of 4 KB pages
- records inside pages

