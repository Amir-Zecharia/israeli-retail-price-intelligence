# Deployment and operating runbook

## Verified local state

Use the README's Python 3.12/PostgreSQL 17 setup and `scripts/local.py` helper.
The local dashboard is configured with `READ_DATABASE_URL`; ingestion alone uses
`DATABASE_URL`. Placeholder variable names are in `.env.example`. The project does
not automatically load `.env`. A missing read-only configuration produces a safe
configuration state rather than using an administrator connection.

The user's direction is to review a working local application **before publication**.
There is no verified public repository, Supabase deployment, Streamlit public URL,
cloud ingestion result or scheduled execution. The prepared workflows are source
files, not operational evidence.

## Hosted release checklist — pending authorization and execution

1. Review the concrete local app and tests. Obtain publication authorization after
   that review. Inspect the exact outgoing file set for secrets, personal paths and
   data rights; retain private `.local/`, `data/`, `.env`, Streamlit secrets and raw
   artifacts outside version control. Keep source attribution and code licensing.
2. Create the Supabase project in the authorized account. Verify its current plan,
   region, connection method, storage and access policies. Use the actual platform
   connection instructions; determine whether the runner and Streamlit require a
   direct or session-pooler connection and validate transaction behavior. Do not
   assume a local Unix-socket DSN applies to hosting.
3. Apply migrations with a migration/admin credential from a secure local environment:
   `python -m database.connection` with `DATABASE_URL` exported privately. The role
   creation/grants in migrations require sufficient privileges. Create separate
   LOGIN credentials assigned to `irpi_ingestor` and `irpi_reader` using the provider's
   supported role controls. Do not give dashboard login membership in ingestor/admin.
   Verify reader SELECT and denied writes; verify ingestion can perform required
   transactions without DDL privileges. Keep migration credentials out of hosting.
4. Publish the reviewed source repository when authorized. Set repository Actions
   secret **INGESTION_DATABASE_URL** to the dedicated ingestion DSN. No provider API
   key is required by the currently implemented public official adapters. If a new
   provider requires a key, use its hosting secret store and update documentation;
   do not add a guessed credential name or secret value to the repository.
5. Run CI and manually run the separate source-probe workflow on a GitHub-hosted
   runner. Inspect the exact source access, parsing and coverage artifacts. Local
   accessibility is insufficient evidence. If a source denies hosted access, stop
   that adapter and investigate supported alternatives without bypassing restrictions.
6. Manually dispatch daily ingestion. Check logs, reconciled counters, publication,
   genuine dates, source provenance and Supabase records. Repeat once to verify
   same-day revision/idempotency. Test a safe failure in a disposable environment;
   production data must remain correctly published.
7. Deploy `app/main.py` through Streamlit Community Cloud using `requirements.txt`.
   Configure **READ_DATABASE_URL** in Streamlit's secret settings using a dedicated
   read-only DSN and provider-required SSL settings. Never configure ingestion/admin
   credentials in the public dashboard process. App secrets must be TOML strings;
   keep real values in the platform, not this document or screenshots.
8. Open the resulting URL in a separate unauthenticated browser, inspect all six
   routes and mobile-width layouts, and reconcile displayed counts/basket totals
   with SQL in the hosted database. Record the real public URL, Actions run URLs,
   UTC verification timestamps and actual screenshots only after success.
9. Observe an actual scheduled invocation separately. A manual dispatch does not
   establish schedule operation. The prepared cron is `15 7 * * *` (07:15 UTC);
   Israeli local time changes with daylight saving. Check workflow scheduling state,
   permissions and account limits using the actual provider dashboards.

## Limits and capacity

Current free-tier quotas have **not been re-verified for a hosted release**. At
release time record the retrieval date and actual account plan, database storage
cap/usage and inactivity behavior, Streamlit resource/hibernation behavior, GitHub
Actions runtime/scheduling limitations and source limits. Do not present assumed
numerical limits or free-tier uptime guarantees as facts. Consult the providers'
current official plan documentation and account controls at that time.

Useful operator SQL (run with suitable monitoring privileges):

```sql
SELECT current_database(), pg_database_size(current_database()) AS database_bytes;
SELECT relname,
       pg_total_relation_size(relid) AS table_and_index_bytes
FROM pg_catalog.pg_statio_user_tables
ORDER BY table_and_index_bytes DESC;
SELECT count(*) AS retained_observations FROM price_observations;
SELECT count(*) AS published_observations FROM published_prices;
```

Compare actual measured usage against the **current account plan's verified cap**,
not an assumed generic free-tier allowance. Measure database/table/index bytes with PostgreSQL `pg_database_size`,
`pg_total_relation_size` and row counts after genuine ingestion. Track bytes per
retained observation including revision and index overhead. The target 1,500 rows
per day is about 547,500 observations per year before revisions/metadata; it is a
capacity projection, not current coverage. Establish warning thresholds below the
actual account cap, monitor failed/partial runs and missing publication dates, and
reduce future collection scope through a new manifest version if required. Do not
silently delete history to conceal capacity pressure. Alerts/report delivery are
not currently configured.

## Recovery, backup and rollback

- Local status: `python scripts/local.py status`. The quality route separates last
  success, latest attempt, failures and missing dates. Read current errors before
  rerunning; repeated source denial is not a reason to bypass access controls.
- Current-date recovery: `python scripts/local.py ingest`, or manual dispatch of
  daily ingestion when hosting is verified. Reruns preserve old revisions and move
  the publication pointer only after a complete accepted revision. There is no
  supported CLI for fabricating backdated observations from current source files.
- Local backup: `python scripts/local.py backup` writes ignored
  `data/local_snapshot.sql` with private file permissions. Copy it to a user-approved
  private backup location. Stop Streamlit before stopping PostgreSQL. Do not treat
  `.gitignore` as a backup system.
- Restore: stop the app, preserve existing data and restore the dump into a **new
  disposable database/cluster** with PostgreSQL 17 tools and `ON_ERROR_STOP=1`;
  create required `irpi_reader`/`irpi_ingestor` roles first. Verify migration checksums,
  counts, dates and reader permissions, then switch the configured connection after
  review. The helper restores its private snapshot automatically only when the real
  database is fresh. Never overwrite a live database without a recoverable backup.
- Hosted backups: use the actual Supabase plan's supported backup/export controls;
  perform a separate restore drill before claiming recoverability. No hosted backup
  or restore has yet been verified.
- Code rollback: preserve the database, select the previously tested code release,
  and run compatible tests against a disposable restored database first. Applied
  migrations are checksum-protected and must not be edited; use a new corrective
  migration. There is no automatic destructive down-migration or cloud rollback.

The local environment depends on this computer. Independent public operation remains
a separate mandatory release gate, not satisfied by local tests.
