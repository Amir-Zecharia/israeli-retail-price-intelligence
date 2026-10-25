-- Protect both sides of membership moves, not only the previous parent.
CREATE OR REPLACE FUNCTION guard_used_sample() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' AND EXISTS(SELECT 1 FROM ingestion_runs WHERE sample_id=OLD.sample_id) THEN
   RAISE EXCEPTION 'Used sample is immutable; create a new version' USING ERRCODE='23514';
 END IF;
 IF TG_OP <> 'DELETE' AND EXISTS(SELECT 1 FROM ingestion_runs WHERE sample_id=NEW.sample_id) THEN
   RAISE EXCEPTION 'Used sample is immutable; create a new version' USING ERRCODE='23514';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION guard_basket_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='baskets' THEN
   IF OLD.sealed THEN RAISE EXCEPTION 'Sealed basket version is immutable' USING ERRCODE='23514'; END IF;
 ELSE
   IF TG_OP <> 'INSERT' AND (SELECT sealed FROM baskets WHERE basket_id=OLD.basket_id) THEN
     RAISE EXCEPTION 'Sealed basket version is immutable' USING ERRCODE='23514';
   END IF;
   IF TG_OP <> 'DELETE' AND (SELECT sealed FROM baskets WHERE basket_id=NEW.basket_id) THEN
     RAISE EXCEPTION 'Sealed basket version is immutable' USING ERRCODE='23514';
   END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;

CREATE FUNCTION guard_product_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.gtin IS DISTINCT FROM NEW.gtin THEN
   RAISE EXCEPTION 'Product identity is immutable; create a distinct product' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_product_identity BEFORE UPDATE OF gtin ON products
 FOR EACH ROW EXECUTE FUNCTION guard_product_identity();
