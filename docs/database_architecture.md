# Database architecture

`python -m database.connection` applies ordered migrations using `DATABASE_URL`. The runner holds a transaction advisory lock, applies all pending migrations atomically, records SHA-256, and rejects edits to previously applied migrations. New changes require a new numbered migration.

Migrations operate in PostgreSQL's `public` schema. Run tests against a dedicated disposable database via `TEST_DATABASE_URL`; fixture tests use disposable irpi_test only; some fixtures are transaction-scoped while analytical fixtures can persist until the disposable test schema is reset. Never point tests at irpi_local or a hosted production database. Production data must never be used for fixtures.

The application normalizes providers, chains, branches, products and selections. Prices reference an immutable run and store descriptive snapshots so dimension corrections do not change historical labels. Source file provenance can be followed from each price to its exact downloaded artifact hash. Daily publication pointers separate collection attempts from observations permitted in analytical results.

Initial indexes support primary/foreign identity uniqueness, product/store filtering, date filtering, unresolved runs and quality issue retrieval. Their actual usefulness must be measured by analytics EXPLAIN evidence in the SQL phase; no performance claim follows from schema design alone.

The database enforces positive prices/quantities, namespaced identities, sample membership, append-only observations, immutable terminal runs, complete-only publication and count consistency. Pipeline transactions, locks and declared fixed sample/basket versions provide additional operational semantics.
