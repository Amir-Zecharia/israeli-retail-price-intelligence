CREATE TABLE sources (
 source_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL UNIQUE, attribution text NOT NULL, base_url text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE retail_chains (
 chain_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id bigint NOT NULL REFERENCES sources,
 source_chain_identifier text NOT NULL CHECK(length(source_chain_identifier)>0),
 chain_name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_id,source_chain_identifier)
);
CREATE TABLE stores (
 store_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 chain_id bigint NOT NULL REFERENCES retail_chains,
 source_store_identifier text NOT NULL CHECK(length(source_store_identifier)>0),
 store_name text NOT NULL, city text, address text, active_status boolean NOT NULL DEFAULT true,
 UNIQUE(chain_id,source_store_identifier)
);
CREATE TABLE categories (
 category_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 category_name text NOT NULL UNIQUE, parent_category_id bigint REFERENCES categories
);
CREATE TABLE products (
 product_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 gtin text UNIQUE CHECK(gtin ~ '^([0-9]{8}|[0-9]{12}|[0-9]{13}|[0-9]{14})$'),
 product_name text NOT NULL, manufacturer text, category_id bigint REFERENCES categories,
 quantity numeric(14,4) CHECK(quantity>0), unit text, normalized_description text,
 matching_status text NOT NULL DEFAULT 'verified_gtin' CHECK(matching_status IN ('verified_gtin','unverified','retailer_specific')),
 CHECK(matching_status <> 'verified_gtin' OR gtin IS NOT NULL)
);
CREATE TABLE source_products (
 chain_id bigint NOT NULL REFERENCES retail_chains,
 source_product_identifier text NOT NULL,
 product_id bigint NOT NULL REFERENCES products,
 mapping_method text NOT NULL DEFAULT 'gtin_checksum',
 PRIMARY KEY(chain_id,source_product_identifier)
);
CREATE TABLE samples (
 sample_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL, version integer NOT NULL CHECK(version>0),
 selection_method text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(name,version)
);
CREATE TABLE sample_stores (
 sample_id bigint REFERENCES samples, store_id bigint REFERENCES stores,
 PRIMARY KEY(sample_id,store_id)
);
CREATE TABLE sample_products (
 sample_id bigint REFERENCES samples, product_id bigint REFERENCES products,
 PRIMARY KEY(sample_id,product_id)
);
CREATE TABLE baskets (
 basket_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL, version integer NOT NULL CHECK(version>0),
 description text NOT NULL DEFAULT '', sealed boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(name,version)
);
CREATE TABLE basket_items (
 basket_id bigint REFERENCES baskets, product_id bigint REFERENCES products,
 quantity numeric(14,4) NOT NULL CHECK(quantity>0), PRIMARY KEY(basket_id,product_id)
);
CREATE TABLE ingestion_runs (
 ingestion_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 sample_id bigint NOT NULL REFERENCES samples,
 observation_date date NOT NULL,
 revision integer NOT NULL CHECK(revision>0),
 started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 status text NOT NULL DEFAULT 'started' CHECK(status IN ('started','complete','partial','failed','abandoned')),
 expected_partitions integer NOT NULL CHECK(expected_partitions>0),
 fetched_partitions integer NOT NULL DEFAULT 0 CHECK(fetched_partitions>=0),
 records_received integer NOT NULL DEFAULT 0 CHECK(records_received>=0),
 records_accepted integer NOT NULL DEFAULT 0 CHECK(records_accepted>=0),
 records_rejected integer NOT NULL DEFAULT 0 CHECK(records_rejected>=0),
 records_duplicate integer NOT NULL DEFAULT 0 CHECK(records_duplicate>=0),
 error_message text, manifest jsonb NOT NULL DEFAULT '{}',
 UNIQUE(sample_id,observation_date,revision),
 UNIQUE(sample_id,observation_date,ingestion_run_id),
 CHECK(fetched_partitions <= expected_partitions),
 CHECK(status='started' OR completed_at IS NOT NULL),
 CHECK(status<>'complete' OR (fetched_partitions=expected_partitions AND records_received=records_accepted+records_rejected+records_duplicate))
);
CREATE TABLE source_files (
 source_file_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 ingestion_run_id uuid NOT NULL REFERENCES ingestion_runs,
 store_id bigint NOT NULL REFERENCES stores,
 source_url text NOT NULL, sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 source_updated_at timestamptz, collected_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(ingestion_run_id,store_id), UNIQUE(source_file_id,ingestion_run_id,store_id)
);
CREATE TABLE price_observations (
 observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 ingestion_run_id uuid NOT NULL REFERENCES ingestion_runs,
 store_id bigint NOT NULL REFERENCES stores, product_id bigint NOT NULL REFERENCES products,
 price_ils numeric(14,4) NOT NULL CHECK(price_ils>0 AND price_ils<10000000),
 collected_at timestamptz NOT NULL DEFAULT now(), source_updated_at timestamptz,
 source_file_id bigint, source_product_identifier text,
 product_name_snapshot text NOT NULL, store_name_snapshot text NOT NULL, chain_name_snapshot text NOT NULL,
 category_name_snapshot text, quantity_snapshot numeric(14,4), unit_snapshot text,
 UNIQUE(ingestion_run_id,store_id,product_id),
 FOREIGN KEY(source_file_id,ingestion_run_id,store_id) REFERENCES source_files(source_file_id,ingestion_run_id,store_id)
);
CREATE TABLE data_quality_issues (
 issue_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 ingestion_run_id uuid NOT NULL REFERENCES ingestion_runs,
 severity text NOT NULL CHECK(severity IN ('info','warning','error')),
 issue_type text NOT NULL, affected_entity text, details jsonb NOT NULL DEFAULT '{}',
 detected_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE daily_publications (
 sample_id bigint NOT NULL, observation_date date NOT NULL, ingestion_run_id uuid NOT NULL UNIQUE,
 PRIMARY KEY(sample_id,observation_date),
 FOREIGN KEY(sample_id,observation_date,ingestion_run_id) REFERENCES ingestion_runs(sample_id,observation_date,ingestion_run_id)
);
CREATE FUNCTION guard_publication() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r ingestion_runs;
BEGIN
 SELECT * INTO r FROM ingestion_runs WHERE ingestion_run_id=NEW.ingestion_run_id FOR UPDATE;
 IF r.status <> 'complete' THEN RAISE EXCEPTION 'Only complete runs may publish' USING ERRCODE='23514'; END IF;
 IF (SELECT count(*) FROM price_observations WHERE ingestion_run_id=r.ingestion_run_id) <> r.records_accepted THEN
 RAISE EXCEPTION 'Accepted count does not match observations' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER valid_publication BEFORE INSERT OR UPDATE ON daily_publications FOR EACH ROW EXECUTE FUNCTION guard_publication();
CREATE FUNCTION guard_observation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rid uuid; sid bigint; rstatus text;
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Observations are append-only' USING ERRCODE='23514'; END IF;
 rid := NEW.ingestion_run_id;
 SELECT sample_id,status INTO sid,rstatus FROM ingestion_runs WHERE ingestion_run_id=rid FOR UPDATE;
 IF rstatus <> 'started' THEN RAISE EXCEPTION 'Run no longer accepts observations' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS(SELECT 1 FROM sample_stores WHERE sample_id=sid AND store_id=NEW.store_id) OR
 NOT EXISTS(SELECT 1 FROM sample_products WHERE sample_id=sid AND product_id=NEW.product_id) THEN
 RAISE EXCEPTION 'Observation outside sample manifest' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_observation BEFORE INSERT OR UPDATE OR DELETE ON price_observations FOR EACH ROW EXECUTE FUNCTION guard_observation();
CREATE FUNCTION guard_terminal_run() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status <> 'started' THEN RAISE EXCEPTION 'Terminal runs are immutable' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_terminal_run BEFORE UPDATE OR DELETE ON ingestion_runs FOR EACH ROW EXECUTE FUNCTION guard_terminal_run();
CREATE FUNCTION guard_used_sample() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE sid bigint;
BEGIN
 IF TG_OP='INSERT' THEN sid := NEW.sample_id; ELSE sid := OLD.sample_id; END IF;
 IF EXISTS(SELECT 1 FROM ingestion_runs WHERE sample_id=sid) THEN
 RAISE EXCEPTION 'Used sample is immutable; create a new version' USING ERRCODE='23514'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER immutable_sample_stores BEFORE INSERT OR UPDATE OR DELETE ON sample_stores FOR EACH ROW EXECUTE FUNCTION guard_used_sample();
CREATE TRIGGER immutable_sample_products BEFORE INSERT OR UPDATE OR DELETE ON sample_products FOR EACH ROW EXECUTE FUNCTION guard_used_sample();
CREATE TRIGGER immutable_sample BEFORE UPDATE OR DELETE ON samples FOR EACH ROW EXECUTE FUNCTION guard_used_sample();
CREATE VIEW published_prices AS
 SELECT o.*,d.sample_id,d.observation_date,r.revision,s.chain_id,c.source_id,p.gtin
 FROM daily_publications d JOIN ingestion_runs r USING(ingestion_run_id)
 JOIN price_observations o USING(ingestion_run_id)
 JOIN stores s USING(store_id) JOIN retail_chains c USING(chain_id) JOIN products p USING(product_id);
CREATE INDEX observation_product_store_idx ON price_observations(product_id,store_id);
CREATE INDEX publication_date_idx ON daily_publications(observation_date);
CREATE INDEX run_started_idx ON ingestion_runs(started_at) WHERE status='started';
CREATE INDEX dq_run_idx ON data_quality_issues(ingestion_run_id);
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='irpi_reader') THEN CREATE ROLE irpi_reader NOLOGIN; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='irpi_ingestor') THEN CREATE ROLE irpi_ingestor NOLOGIN; END IF;
END $$;
GRANT USAGE ON SCHEMA public TO irpi_reader,irpi_ingestor;
CREATE VIEW run_status AS SELECT ingestion_run_id,sample_id,observation_date,revision,started_at,completed_at,status,expected_partitions,fetched_partitions,records_received,records_accepted,records_rejected,records_duplicate FROM ingestion_runs;
CREATE VIEW quality_summary AS SELECT issue_id,ingestion_run_id,severity,issue_type,detected_at FROM data_quality_issues;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO irpi_ingestor;
GRANT SELECT ON published_prices,run_status,quality_summary,sources,retail_chains,stores,categories,products,samples,sample_stores,sample_products,baskets,basket_items,daily_publications TO irpi_reader;
GRANT INSERT,UPDATE ON sources,retail_chains,stores,categories,products,source_products,samples,sample_stores,sample_products,baskets,basket_items,ingestion_runs,source_files,price_observations,data_quality_issues,daily_publications TO irpi_ingestor;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO irpi_ingestor;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE FUNCTION guard_basket_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE bid bigint;
BEGIN
 IF TG_TABLE_NAME='baskets' THEN
   IF OLD.sealed THEN RAISE EXCEPTION 'Sealed basket version is immutable' USING ERRCODE='23514'; END IF;
 ELSE
   IF TG_OP='INSERT' THEN bid := NEW.basket_id; ELSE bid := OLD.basket_id; END IF;
   IF (SELECT sealed FROM baskets WHERE basket_id=bid) THEN
     RAISE EXCEPTION 'Sealed basket version is immutable' USING ERRCODE='23514'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER immutable_basket BEFORE UPDATE OR DELETE ON baskets FOR EACH ROW EXECUTE FUNCTION guard_basket_version();
CREATE TRIGGER immutable_basket_items BEFORE INSERT OR UPDATE OR DELETE ON basket_items FOR EACH ROW EXECUTE FUNCTION guard_basket_version();
