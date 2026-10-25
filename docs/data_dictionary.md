# Data dictionary

PostgreSQL is authoritative. IDs are internal bigint identities except UUID ingestion runs. All identifiers received from providers and GTINs remain text, preserving leading zeros. Currency is ILS `numeric(14,4)`, never float. Zero/negative prices fail validation rather than represent missing prices. All timestamps are timezone-aware; connection sessions default UTC. `observation_date` is the explicit Israel collection date and is not inferred from the database server's timezone.

| Table | Grain / meaning |
|---|---|
| sources | Provider and attribution |
| retail_chains | Provider + external chain identifier |
| stores | Internal chain + external store identifier; same external store code across chains is valid |
| categories | Named category, optional parent |
| products | Canonical product; GTIN string unique when present; matching status declares identity confidence |
| source_products | External identifier scoped to chain (and transitively source) → canonical product |
| samples | Named, numbered immutable-after-use sample version and selection method |
| sample_stores | Expected branch manifest for a sample version |
| sample_products | Expected product manifest for a sample version |
| baskets | Named, numbered basket definition |
| basket_items | Product and strictly positive package count within a basket version |
| ingestion_runs | Attempt UUID, sample/date/revision, lifecycle, partition and record counters, diagnostic manifest |
| source_files | Per-run/store provenance URL, SHA-256, collection and source times |
| price_observations | One accepted run/store/product observation; immutable snapshots of product/store/chain names, category, quantity and unit |
| data_quality_issues | Structured severity, type, entity and JSON evidence per run |
| daily_publications | Exactly one published run pointer per sample and Israel observation date |
| published_prices | Analytical view restricted to current publication pointers, with sample/date/revision and namespaced dimensions |
| schema_migrations | Applied migration name, checksum and timestamp |

A product GTIN format constraint is intentionally insufficient for exact matching alone: ingestion must verify GTIN checksum and provider item type before assigning `verified_gtin`. Unknown and retailer-specific items may be stored separately but do not belong in exact-match comparisons. Missing observations have no row and must be measured against the sample manifest.

## Daily policy

Each attempt receives a monotonically allocated revision under a sample/date application lock. Observations are append-only and may enter only a `started` run. The pipeline atomically inserts observations, sets reconciled terminal counters, and publishes a complete run. Publication checks the accepted count against actual rows. Failed/partial attempts stay diagnostic and cannot publish. A later successful same-day revision replaces the pointer, retaining prior run observations for audit. Analytics must read `published_prices`; raw observations include superseded attempts and must not be summed indiscriminately.

`records_received = records_accepted + records_rejected + records_duplicate` for complete runs. `expected_partitions = fetched_partitions` for complete runs; missing products in an otherwise fetched partition are coverage limitations rather than invented prices. Terminal runs and observations cannot be mutated. Metadata snapshots ensure renaming a dimension does not rewrite descriptive history.

## Access

Migration owner requires permission to create objects and NOLOGIN group roles. `irpi_ingestor` gets data SELECT/INSERT/UPDATE and sequence USAGE; `irpi_reader` gets SELECT only. Neither receives migration-table write access or public-schema CREATE. Assign a separate LOGIN to the appropriate group during deployment; do not use the owner credential in the dashboard. Role provisioning and hosted-provider compatibility remain deployment checks.
