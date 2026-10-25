# SQL analysis and reproducibility

PostgreSQL computes all measures. `database/analytics.py` provides an allow-listed,
parameterized `query(name, **filters)` service; no user input enters SQL identifiers.
Inclusive filters cover sample version, dates, product, snapshot category, declared
chains/stores and sealed basket version. Queries return at most 10,000 rows (default
1,000); the interface must label bounded exports. `None` selects all; an empty ID
list selects none. `options()` supplies metadata and available dates.

All SQL reads `published_prices`, which resolves exactly one complete revision per
sample/date. Same-day revisions are not extra historical observations. The reusable
`published_price_changes` view exposes observed LAG transitions and is readable by
`irpi_reader`; migration 003 adds it without editing applied migrations. Services
use snapshot labels, not today's mutable product descriptions. GTIN identity is
immutable. Cross-chain comparisons require a non-NULL canonical GTIN.

## A — Latest valid price

Question: what was most recently observed for each selected product/store by the
cutoff? `database/analytics/latest_prices.sql` uses DISTINCT ON ordered by date and
observation ID, returns the original price, collection/source timestamps, observation
date and `age_days`. It searches before the start filter so a historical last value
can be displayed with its age. This is explicitly an observed price, never a
forward-filled input to comparisons or baskets. The cutoff prevents future leakage.

## B — Observed changes

Question: which prices changed between observations?
`database/analytics/price_changes.sql` uses LAG partitioned by product/store over
the selected period. `previous_price`, `previous_date`, `change_ils`, `change_pct`
and `gap_days` define the observation interval; `first_detected_change_date` is
when a change was first detected within that period, not its actual effective date.
The initial row has NULL deltas. Missing dates never create rows or zero prices.
Changing the period can exclude the prior observation, intentionally yielding NULL.

## C — Matched retailer comparison

Question: how do selected branches price identical products on the same date?
`database/analytics/retailer_comparison.sql` takes the median of the declared
selected branches for each product/date/chain and pairs canonical products across
chains. Gaps equal first-chain minus comparison-chain; percentage denominator is
comparison-chain price. Outputs include matched count, selected count, branch
counts, tied dense price rank and the median of paired product percentage gaps.
The branch statistic is an equally weighted median, not a cheapest-store selection.

`fixed_panel_eligible` is true only if a product is observed for every selected
branch of every selected chain on **every published date** in the chosen period.
Its definition is fixed for that whole query. Available-pair rows remain visible
with this flag false, making complete-versus-available sensitivity reproducible.
Calendar missing dates are independently exposed; eligibility does not imply daily
collection. Single-chain selection has no pairwise comparison. No national inference
is justified by a small convenience sample.

## D — Price volatility

Question: how often and how much did prices move?
`database/analytics/price_volatility.sql` reports observation/pair counts, nonzero
change frequency per observed pair, median absolute percentage among nonzero
changes, signed maximum/minimum changes, maximum observation gap and consecutive-day
pair count/frequency. One date yields NULL frequency and magnitudes, not stability.
Two dates describe one transition and cannot establish a stable retailer profile.
These are descriptive movements, not inflation or proven promotional effects.

## E — Category pricing

Question: which snapshot categories show larger paired gaps?
`database/analytics/category_pricing.sql` aggregates **matched products**, never
unmatched category totals. Mean ILS and percentage gaps and median percentage gap
come with matched/fixed-panel product counts and branch coverage. Product selection
can change the result; compare fixed-panel counts, alternate declared store IDs and
product subsets through the same parameterized query. Percentage means weight each
matched product equally, not its spending share. NULL snapshot categories remain
an explicit unlabeled group.

## F — Versioned baskets

Question: what does a fixed quantity basket cost at each selected store/chain/date?
`database/analytics/basket_costs.sql` builds a grid of published dates, declared
stores and sealed basket items, left joining exact same-date observations. It
returns required/observed counts, coverage, missing product IDs and observed subtotal.
`comparable_total` exists only at 100% item coverage. A quantity of two contributes
twice its exact price. Product/category filters can only remove observed matches;
they never silently shrink required basket membership. Version identifies immutable
composition. Chain total is the median of complete store baskets **only when every
selected branch has a complete basket**; branch counts and coverage accompany it.
Missing calendar days are not filled. No substitutions occur.

## G — Investigation signals

Question: which observations merit inspection?
`database/analytics/price_anomalies.sql` returns observed evidence and flags rather
than hiding unflagged rows. A large change needs both a configurable ILS threshold
(default 2) and absolute percentage threshold (default 20); doubled thresholds
provide sensitivity. Repeated increase means two positive observed transitions;
gaps remain visible. Branch deviation compares a branch to its same-date chain
median with at least two observed branches and both thresholds. Highly variable
requires at least three observed pairs and a mean absolute percentage movement
above the relative threshold. These screening rules are not statistical significance,
proof of data error, a promotion, misconduct or collusion. One-branch samples cannot
estimate within-chain spread.

## H — Transparent profiles

Question: how do observed retailer measures differ?
`database/analytics/pricing_profiles.sql` returns a relative median price level
against the date/product mean across selected chains, computed on the fixed common
panel; observed change frequency; mean absolute movement; branch spread only when
at least two branches are observed; product coverage; observed-date counts. Measures
remain separate. There is no arbitrary composite behavior score. The relative level
is descriptive of matched pilot products and equal branch medians, not market share.

## Dashboard and quality SQL

`overview.sql` computes counts, calendar-panel coverage, dates, transitions, last
successful completion and latest attempt status separately. Calendar coverage's
denominator is days × declared stores × selected products. Category selection fixes
product membership using each manifest product's last published snapshot at/before
the cutoff, across the sample; if no snapshot has ever existed, the current reference
category is an explicit fallback for the still-unobserved manifest product. A NULL
snapshot category stays NULL. Category membership is fixed across the selected
period and filters both numerator and expected denominator; it never derives the
panel merely from observed rows in the selected interval. `missing_days.sql`
returns every date plus a missing-publication flag. `ingestion_quality.sql` exposes
all attempts in the period, publication status, rejected counts/rate, partition
coverage and issue counts. Failed attempts cannot replace the published data.

## Local genuine findings — 24 October 2026

Reproduce with `database.analytics.query` against the local database. Complete raw
outputs and actual plans are preserved in `artifacts/analytics_local_evidence.json`.
This pilot comprises **11 verified products, two stores, one store per chain and
one genuine observation date**, with 22 published rows and 100% manifest coverage.
The retained same-day revision is not a second observation day.

1. Which selected store has the cheaper fixed basket? The eleven-item, quantity-one
   basket costs **₪132.80 at the selected Shufersal store and ₪109.40 at the selected
   Carrefour store**, a ₪23.40 gap. Both baskets have 11/11 products. This does not
   establish which chain is consistently cheaper across branches or time.
2. Which observed category has the larger paired per-product gap? Packaged food
   (nine matched products) has a **₪2.22 mean product gap and 31.11% median gap**;
   dairy/substitutes (two matched products) has a **₪1.70 mean gap and 17.73% median
   gap**, Shufersal minus Carrefour. The categories have unequal sample sizes;
   percentage median is not a category basket premium or spending-weighted estimate.
3. Can price stability or intra-chain branch variability be estimated? **No**:
   zero temporal transitions and one store per chain leave change frequency and
   branch-spread profiles NULL. The database correctly exposes insufficient history
   rather than labeling prices stable. Daily collection must accrue genuine dates.

## Verification and performance

`tests/integration/test_analytics.py` executes all eleven SQL services under actual
PostgreSQL, also with `SET ROLE irpi_reader`. Hand-calculated fixtures cover missing
Jan 2, observed two-day LAG gaps, initial NULL transitions, same-date branch medians,
tied ranks, fixed-panel exclusion, multi-quantity ₪80 baskets, 50%-covered subtotal
without comparable total, cutoff bounds, empty selections and threshold sensitivity.
Fixtures reside only in irpi_test. Production never receives synthetic history.

The real 22-row pilot plans for comparison, basket and volatility are recorded with
EXPLAIN (ANALYZE, BUFFERS). Such small input cannot justify elaborate indexes. A
separate 100,000-row temporary-table selectivity experiment in irpi_test measured
an exact `(product_id,store_id)` lookup: sequential scan **3.309 ms / 576 local
buffer hits** versus index scan **0.020 ms / one hit and two reads**, in one local
run. The temporary table disappeared when its session closed. This demonstrates
why existing `observation_product_store_idx` is useful for selective product/store
lookups; it is not an end-to-end production latency benchmark or cache-controlled
claim. No redundant production index was added. Full dashboards still depend on
run/date joins and selected period; inspect real plans as retained history grows.
