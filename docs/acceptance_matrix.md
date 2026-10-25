# Acceptance matrix

This maps the original brief to implemented paths and actual evidence. **Local**
means verified in the local environment, not cloud deployment. Overall public-product
acceptance remains pending. User direction explicitly defers publication until local
review; the original run and unfulfilled hosted gates remain intact.

| Requirement / brief section | Implementation and documentation | Evidence / state |
|---|---|---|
| Genuine source feasibility (3, Phase0) | `pipeline/extract`, `docs/source_feasibility.md` | Local real official records from two chains; source proof16tests; hosted access pending |
| Reproducible controlled pilot (4) | `config/pilot_v1.json`, `docs/methodology.md` | Eleven reviewed products, two chains/two source branches; larger target pending |
| Relational schema, constraints, UTC/NUMERIC (5) | `database/migrations/001_foundation.sql`, `002_immutable_identity.sql`, `database/connection.py`, data dictionary | Actual PostgreSQL17 integrity/permission tests; checked additive migrations |
| Transactions, identity, retry/failure/concurrency (6) | `pipeline/ingest.py`, extraction adapter, pipeline tests | Two genuine complete same-day revisions;22published rows; failure/partial/concurrency fixtures in irpi_test |
| Genuine history and provenance (5,9) | immutable observations, source files, daily publication | Actual source hashes/snapshots; one genuine date; longitudinal findings insufficient |
| SQL A–H (7) | `database/analytics/*.sql`, `database/analytics.py`, migration003, SQL analysis | Hand-calculated real PostgreSQL integration tests; all services verified with reader role; actual EXPLAIN evidence |
| Fixed basket/missing-data/common-panel reliability (7,9) | basket SQL, fixed panel CTEs, versioned manifest/basket | Quantity/missing basket/gap/tie/category-denominator fixtures; no zero substitution/forward fill |
| Six pages (English per latest user direction) (8) | `app/main.py`, `app/data.py`, `app/ui.py`, dashboard documentation | Streamlit smoke tests cover six populated routes, empty/one-day/error/filter states; browser visual evidence recorded separately |
| Search/filters/charts/CSV/cache/freshness (8) | app UI + parameterized SQL | Smoke tests, formula-safe export tests;60-second cache; bounded output |
| Read-only dashboard/security (12) | dedicated `READ_DATABASE_URL`, irpi_reader grants, `.env.example` | Actual irpi_dashboard LOGIN query/options and read-only six-page smoke checks; hosted secrets pending |
| Automated tests (10) | `tests`, `.github/workflows/ci.yml` |53 tests passed in 3.22s after English conversion, including real read-only rendering; hosted CI pending |
| Reproducible local setup/backup (11,12) | `scripts/local.py`, README, deployment runbook | Canonical project restored into its own cluster;51tests passed;22published observations and one date;app running locally |
| Daily/manual scheduler (6,12) | `.github/workflows/daily_ingestion.yml`, `source_probe.yml` | Files prepared; no hosted dispatch or actual schedule observed |
| Supabase and public Streamlit URL (12, Phase5) | `docs/deployment.md` | **Pending user local review and publication authorization, then account setup and actual verification** |
| Independent cloud ingestion/browser access (12,16) | release checklist | **Pending; local collection does not satisfy this gate** |
| Current free-tier quotas/capacity/recovery (12) | deployment runbook | Verification procedure documented; current account limits, monitoring and hosted restore drill pending |
| English README/diagram/3real findings (15, Phase6) | README, architecture, SQL analysis, limitations | Genuine basket/category/largest-product findings documented; no fabricated public URL or screenshots |
| Screenshots (15) | real local visual review evidence | Actual local overview captured at docs/screenshots/overview.jpg; hosted screenshots pending |
| Licensing/attribution | LICENSE, source feasibility | Original code MIT; third-party data and brands excluded; broader source-use verification pending |
| Advanced weekly reports/behavior index (13, Phase7) | deferred | Optional; insufficient genuine history and mandatory hosted gates not yet passed |

Exact test timings vary by invocation. Consult the development log for recorded
checkpoints; the earlier3.35-second workflow timing was a transcription error and
must not be presented as verification evidence.
