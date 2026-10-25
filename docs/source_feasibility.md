# Source feasibility — 2026-10-24

Status update (2026-10-25): **local official-feed pilot, PostgreSQL ingestion, SQL analytics and English dashboard implemented; GitHub source and CI published; two-source cloud gate and public app deployment pending**. The original investigation below remains dated2026-10-24. The controlled local source selection and branch mapping are documented in methodology; local evidence does not establish hosted accessibility.

## Observed proof

The corrected bounded official-feed probe completed locally at `2026-10-24T08:31:50.625919+00:00`, using four HTTP requests, with no rejected records in the two selected files:

| Publisher | File | XML store ID | Parsed prices | SHA-256 |
|---|---|---|---:|---|
| Shufersal | `PriceFull7290027600007-001-034-20261024-030840.gz` | `034` | 5,986 | `eae8400787d474fe38915c5b7eafee7994838ee5849c239c2b35ae181ea8f115` |
| Carrefour | `PriceFull7290055700007-001-416-20261024-110011.gz` | `134` | 11,087 | `f10620e9ccd65758cf2e32f3f66775d2d1a572aa347205a5c3aecc6a0075ebf7` |

There were 1,784 candidate shared identities after valid GTIN/check-digit, non-weighted item-type and equal nonempty package-field checks. This is a candidate count, not 1,784 independently verified products. Sanitized evidence is retained locally in `artifacts/source_probe_verified_local.json`; signed download URLs are deliberately excluded. Its original generic approval wording predates the diagnostic fix and is not an actual user-approval requirement.

The filenames changed from the parser's assumed three numeric groups to five. Both publishers now use chain, subchain, store, date and time components. Carrefour also uses `PriceUpdateTime` and `ManufactureName`, rather than only the original parser's `PriceUpdateDate` and `ManufacturerName`. Regression tests reproduced these failures before the corrections.

## Source matrix

| Source | Accessibility and actual structure | Authentication / limits | Identity, time and history | Decision |
|---|---|---|---|---|
| [Shufersal official portal](https://prices.shufersal.co.il/) | Public HTML listing, signed HTTPS gzip XML download; real file parsed locally. Earlier timeout/DNS failure was not conclusive evidence of restriction | No login/key in this probe. No numerical rate/monthly quota verified; do not infer unlimited capacity | XML chain/store/product IDs, price and update timestamp. Current file is not historical observations | Candidate official adapter; hosted-runner check pending |
| [Carrefour official portal](https://prices.carrefour.co.il/) | Public HTML JavaScript file manifest, dated directory, gzip XML; real file parsed locally | No login/key in probe. No numerical rate/monthly quota verified | XML IDs, price, package fields and PriceUpdateTime. Filename store differs from XML store in selected file | Candidate official adapter; resolve branch mapping before panel selection |
| [PriceIL API](https://priceil.dev/developers/docs) | Developer documentation and local product metadata request worked. The tested product's prices were empty; no successful PriceIL price-record proof | Documentation describes anonymous access at 20 requests/minute; [plans](https://www.priceil.dev/developers/plans) describes 5,000 monthly requests for free registered usage, while anonymous calls are not counted against that monthly allotment. Re-check before integration | Documented barcode/store IDs. Actual usable price timestamp/history not established by the empty response | Fallback candidate only; no implemented production adapter or redundancy claim |
| [rxradar/israeli-prices](https://github.com/rxradar/israeli-prices) | Public repository and reachability report inspected during investigation; upstream observations are not IRPI cloud evidence | A client library, not a separate data provider; endpoints govern access | Useful reference for retailer-specific layouts; package not used in this proof | Direct minimal adapter chosen for two verified formats; inspect license before copying any code |
| [israeli-supermarket-scarpers](https://github.com/OpenIsraeliSupermarkets/israeli-supermarket-scarpers) | Public README inspected; package not executed in this proof | Client library; per-provider access applies | Coverage/history claims not independently validated | Reference candidate, not tested redundancy |

## Identity review and limitations

The implementing assistant reviewed the following examples directly from the retained response, comparing original barcode, name, manufacturer, quantity and unit. They support the feasibility of exact cross-chain matching; they are not a national basket sample:

| Original barcode | Matching product description | Package | Shufersal / Carrefour observed ILS |
|---|---|---|---|
| `72917329` | Egozi chocolate bar, Strauss | 45 g | 5.90 / 4.50 |
| `72917367` | Taami chocolate bar, Strauss | 40 g | 5.90 / 4.50 |
| `72940754` | Milky vanilla, Strauss | 170 ml | 3.60 / 3.00 |

These values are collected feed observations, not guaranteed checkout prices. Promotions are not modeled by this probe. Original 8-digit codes are retained; canonical comparison keys are zero-padded GTIN-14 strings.

Carrefour's selected filename contains store `416`, while its XML says `134`. The parser preserves the XML identifier; it does not infer a city or address from the filename. Store-list reconciliation must precede a fixed representative panel. The earlier October 23 file also contained names disagreeing with quantity fields (for example, a 40 g name with a 50 g quantity); exclude unresolved packages from the verified comparison basket.

Some source price-update times are months old. They identify the source's last reported price change, not the start of IRPI's history. Collection timestamps are UTC. The interpretation of naive source timestamps as Asia/Jerusalem must remain explicit. No observations before actual collection may be manufactured.

## Access, attribution and retention

Keep publisher, public listing URL, file hash, collection time and source IDs in provenance; attribute official publications in the application. No credentials, proxies, geographic workarounds or rate-limit bypasses were used.

Section 30(e) of the Food Competition Law is the relevant free-use provision: the [published statutory-text mirror](https://www.takdin.co.il/Document/Text?clause=7&id=4550148&lawDate=&maagar=1&packCode=131072) describes free private/commercial use of the published information. The [original Knesset publication](https://fs.knesset.gov.il/19/law/19_lsr_301575.pdf) redirected to a geographical-unavailability page when opened in this research environment. Verify current applicable publication terms before expanding production collection; absence of a published quota is not permission for unlimited requests.

PriceIL's permission for building applications should not be conflated with independently verified historical retention terms. Since official files now work locally, there is no need to rely on an unverified PriceIL retention assumption for this pilot.

## Request and storage budget

The proof requests one listing and one full file per chain: four requests, with at most two attempts per request on network failures, at most eight total attempts. HTTP 403 and 429 are terminal. Each response and decompressed file is bounded at 32 MiB. The probe scans the first bounded listing page only and chooses its latest supported full file; this convenience choice is not a representative fixed branch sample.

The implementation keeps only a small evidence excerpt and hashes, not a fabricated historical dataset. Daily production budgets must include branch manifests, full-file byte sizes, retries and service limits. Increasing coverage requires measurements rather than extrapolating from this two-file proof.

## Verification and remaining gate

- 16 tests pass, covering filename variants, source fields, decimal prices, identity checks, timezone conversion, missing IDs, access denials, bounded retries, byte limits, gzip expansion and explicit failure diagnostics.
- Real local extraction passed for two chains; selected cross-chain identities reviewed above.
- Hosted [source probe run 40177107830](https://github.com/Amir-Zecharia/israeli-retail-price-intelligence/actions/runs/40177107830) executed on 2026-10-25. Shufersal parsed 5,974 records with zero parse rejections; Carrefour failed with ConnectTimeout after bounded attempts. Four total requests were made. No cross-chain matches were available, so the technical gate failed. The diagnostic artifact records the partial result; no access restriction was bypassed.
- Cloud success must be evidenced by an actual run URL and artifact. Local success cannot satisfy this check.
- Local pilot continuation completed after the user-directed gate change: methodology records the fixed source/XML branch mapping, eleven-product panel and source-use limitations; schema, ingestion, SQL and local dashboard now exist. Cloud source verification remains an open release gate under the original Babysitter run.
