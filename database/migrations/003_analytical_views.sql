-- Reusable observed transitions. Snapshot metadata comes from immutable observations.
CREATE VIEW published_price_changes AS
 SELECT p.*,lag(price_ils) OVER w previous_price,
 lag(observation_date) OVER w previous_date
 FROM published_prices p
 WINDOW w AS (PARTITION BY sample_id,store_id,product_id ORDER BY observation_date,observation_id);
GRANT SELECT ON published_price_changes TO irpi_reader,irpi_ingestor;
