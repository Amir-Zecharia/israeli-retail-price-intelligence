# Known limitations

- **Scope:** the genuine initial pilot has two chains, one source partition/branch
  per chain, eleven verified packaged products, two categories and one observation
  date, 24 October 2026. It is a convenience engineering sample dominated by
  confectionery, not representative of national prices, branches or household spend.
  The 3–5-chain, roughly 100-product target has not been met.
- **History:** genuine history starts with actual IRPI collection. Same-day revisions
  are preserved but expose one published date. There are no temporal transitions
  yet, so longitudinal volatility, stable retailer behavior and weekly reports cannot
  be concluded. One branch per chain cannot establish within-chain variability.
- **Branch metadata:** the Carrefour filename partition differs from its XML store
  identifier; both are explicitly mapped and checked. Geography/address are not
  independently verified and remain absent. Expanding representative branch coverage
  requires new evidence and a new immutable sample version.
- **Identity and prices:** comparisons use exact canonical GTIN/package checks and
  exclude ambiguous packages. Metadata review is not physical product verification.
  Prices are published feed observations, not guaranteed checkout prices. Promotions,
  loyalty eligibility, multibuy offers and individual shopping behavior are not modeled.
- **Missing data:** absent prices are NULL/missing coverage, never zero or silent
  forward fills. Fully comparable baskets need all items; chain basket totals require
  all selected branches complete. Fixed common panels are assessed over published
  dates; missing calendar days are separately exposed. No statistical or causal
  significance follows from descriptive gaps or anomaly flags.
- **Sources:** official Shufersal/Carrefour adapters work locally. Cloud geography,
  access policy, changing publication formats and bounded listing discovery can
  prevent collection. PriceIL is a fallback candidate, not a tested redundant adapter.
  Access denial/rate limiting is terminal; restrictions are not bypassed. Current
  source terms need verification before expanded redistribution.
- **Dashboard:** results/exports are bounded to 1,000 rows in the interface; narrow
  filters for detailed inspection. Cache lifetime is 60 seconds and has a refresh
  control. Dates and selected panel affect all analytical interpretations. Category
  membership uses historical labels where known, with a documented reference fallback
  for manifest products never observed. No arbitrary composite behavior score exists.
- **Hosting:** GitHub source publication and CI are verified. The hosted source probe parsed Shufersal but Carrefour timed out, so the two-source cloud gate remains unmet. Supabase, a public Streamlit URL, real hosted database ingestion, current service quotas, independent browser verification, scheduled invocation and hosted recovery remain pending. Free services cannot be assumed to guarantee 24/7 uptime.
- **Operations:** the local helper uses a private Unix socket and local trust under
  restricted directories; it is not a cloud authentication configuration. Snapshots
  and local state are intentionally excluded from Git. Backups must be retained
  separately. Capacity monitoring and hosted alert delivery are release work.

Next priorities are user review of the working local application, verified authorized
hosting, genuine daily history, wider documented fixed panels, and measured capacity.
Optional reports/advanced scores remain deferred until mandatory release gates pass.
