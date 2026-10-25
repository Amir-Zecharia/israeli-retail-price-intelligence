import pytest
import psycopg
from test_database import db, seed


def test_used_sample_rejects_moving_new_members_into_it(db):
    _, _, _, _, sample, _ = seed(db)
    other = db.execute("INSERT INTO samples(name,version,selection_method) VALUES ('Unused',1,'fixture') RETURNING sample_id").fetchone()[0]
    product = db.execute("INSERT INTO products(gtin,product_name) VALUES ('00012345678912','Other') RETURNING product_id").fetchone()[0]
    db.execute('INSERT INTO sample_products VALUES (%s,%s)', (other, product))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute('UPDATE sample_products SET sample_id=%s WHERE sample_id=%s', (sample, other))


def test_sealed_basket_rejects_moving_items_into_it(db):
    _, _, _, product, _, _ = seed(db)
    first = db.execute("INSERT INTO baskets(name,version) VALUES ('Sealed',1) RETURNING basket_id").fetchone()[0]
    second = db.execute("INSERT INTO baskets(name,version) VALUES ('Editable',1) RETURNING basket_id").fetchone()[0]
    db.execute('UPDATE baskets SET sealed=true WHERE basket_id=%s', (first,))
    db.execute('INSERT INTO basket_items VALUES (%s,%s,1)', (second, product))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute('UPDATE basket_items SET basket_id=%s WHERE basket_id=%s', (first, second))


def test_product_identity_cannot_relabel_old_observations(db):
    _, _, _, product, _, _ = seed(db)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("UPDATE products SET gtin='00012345678912' WHERE product_id=%s", (product,))
