WITH panel AS (
 SELECT ss.store_id,s.chain_id FROM sample_stores ss JOIN stores s USING(store_id)
 WHERE ss.sample_id=%(sample_id)s AND (%(chain_ids)s::bigint[] IS NULL OR s.chain_id=ANY(%(chain_ids)s))
 AND (%(store_ids)s::bigint[] IS NULL OR s.store_id=ANY(%(store_ids)s))
), wanted AS (
 SELECT sp.product_id FROM sample_products sp JOIN products prod USING(product_id)
 LEFT JOIN categories cat USING(category_id)
 LEFT JOIN LATERAL (
  SELECT observation_id,category_name_snapshot FROM published_prices pp
  WHERE pp.sample_id=sp.sample_id AND pp.product_id=sp.product_id AND pp.observation_date<=%(end_date)s
  ORDER BY observation_date DESC,observation_id DESC LIMIT 1
 ) label ON true
 WHERE sp.sample_id=%(sample_id)s
 AND (%(product_id)s::bigint IS NULL OR sp.product_id=%(product_id)s)
 AND (%(category)s::text IS NULL OR
 CASE WHEN label.observation_id IS NOT NULL THEN label.category_name_snapshot ELSE cat.category_name END=%(category)s)
), observations AS (
 SELECT p.* FROM published_prices p JOIN panel USING(store_id,chain_id) JOIN wanted USING(product_id)
 WHERE p.sample_id=%(sample_id)s AND p.observation_date BETWEEN %(start_date)s AND %(end_date)s
), changes AS (
 SELECT *,lag(price_ils) OVER w previous_price,lag(observation_date) OVER w previous_date
 FROM observations WINDOW w AS (PARTITION BY product_id,store_id ORDER BY observation_date,observation_id)
), deltas AS (
 SELECT *,price_ils-previous_price change_ils,100*(price_ils-previous_price)/previous_price change_pct,
 observation_date-previous_date gap_days FROM changes
), chain_prices AS (
 SELECT observation_date,chain_id,product_id,min(chain_name_snapshot) chain_name,
 min(product_name_snapshot) product_name,min(category_name_snapshot) category,
 percentile_cont(0.5) WITHIN GROUP(ORDER BY price_ils) median_price,
 count(*) observed_stores,(SELECT count(*) FROM panel q WHERE q.chain_id=o.chain_id) expected_stores,
 max(price_ils)-min(price_ils) branch_spread_ils
 FROM observations o WHERE gtin IS NOT NULL GROUP BY observation_date,chain_id,product_id
), ranked_prices AS (
 SELECT *,dense_rank() OVER(PARTITION BY observation_date,product_id ORDER BY median_price) price_rank
 FROM chain_prices
), fixed_products AS (
 SELECT product_id FROM chain_prices GROUP BY product_id
 HAVING count(*)=(SELECT count(DISTINCT chain_id) FROM panel)*(SELECT count(*) FROM daily_publications WHERE sample_id=%(sample_id)s AND observation_date BETWEEN %(start_date)s AND %(end_date)s)
 AND bool_and(observed_stores=expected_stores)
), pairs AS (
 SELECT a.observation_date,a.product_id,a.product_name,a.category,a.chain_id,a.chain_name,
 b.chain_id comparison_chain_id,b.chain_name comparison_chain_name,
 a.median_price,b.median_price comparison_price,
 a.median_price-b.median_price gap_ils,100*(a.median_price-b.median_price)/b.median_price gap_pct,
 a.price_rank,b.price_rank comparison_price_rank,a.observed_stores,a.expected_stores,b.observed_stores comparison_observed_stores,b.expected_stores comparison_expected_stores,
 a.product_id IN(SELECT product_id FROM fixed_products) fixed_panel_eligible
 FROM ranked_prices a JOIN ranked_prices b USING(observation_date,product_id)
 WHERE a.chain_id<b.chain_id
)
SELECT g.day::date observation_date,d.ingestion_run_id IS NULL missing_publication
 FROM generate_series(%(start_date)s::date,%(end_date)s::date,interval '1 day') g(day)
 LEFT JOIN daily_publications d ON d.sample_id=%(sample_id)s AND d.observation_date=g.day::date
 ORDER BY g.day LIMIT %(limit)s
