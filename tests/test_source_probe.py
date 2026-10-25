"""Synthetic fixtures; none of these prices are collected market evidence."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from pipeline.extract.official import parse_prices, shared_products, gtin14, listing

XML = b'''<root><ChainId>7290027600007</ChainId><StoreId>001</StoreId><Items>
<Item><ItemCode>7290000000008</ItemCode><ItemType>1</ItemType><ItemName>Test milk</ItemName><ItemPrice>6.50</ItemPrice><bIsWeighted>0</bIsWeighted><PriceUpdateDate>2026-10-22 12:00:00</PriceUpdateDate><Quantity>1</Quantity><UnitQty>liter</UnitQty></Item>
</Items></root>'''

class ProbeTests(unittest.TestCase):
    def test_decimal_identifiers_timezone(self):
        rows, rejected = parse_prices(XML, 'shufersal', datetime.now(timezone.utc))
        self.assertEqual(rejected, 0)
        self.assertEqual(rows[0]['price_ils'], '6.50')
        self.assertEqual(rows[0]['store_id'], '001')
        self.assertEqual(rows[0]['source_updated_at'], '2026-10-22T09:00:00+00:00')
        self.assertEqual(rows[0]['gtin'], '07290000000008')
    def test_invalid_price_rejected(self):
        for bad in (b'0', b'-2', b'NaN', b'Infinity', b'bad'):
            rows, rejected = parse_prices(XML.replace(b'6.50',bad), 'shufersal', datetime.now(timezone.utc))
            self.assertEqual((len(rows), rejected), (0,1))
    def test_identity_excludes_internal_weighted_and_bad_check_digit(self):
        self.assertIsNone(gtin14('7290000000009'))
        self.assertIsNone(gtin14('12345'))
        for changed in (XML.replace(b'<ItemType>1',b'<ItemType>0'), XML.replace(b'<bIsWeighted>0',b'<bIsWeighted>1')):
            rows, _ = parse_prices(changed,'shufersal',datetime.now(timezone.utc))
            self.assertIsNone(rows[0]['gtin'])
    def test_shared_requires_distinct_chain_and_consistent_quantity(self):
        a = parse_prices(XML,'shufersal',datetime.now(timezone.utc))[0][0]
        self.assertEqual(shared_products([a,a]), [])
        b = dict(a, chain='carrefour', chain_id='other')
        self.assertEqual(len(shared_products([a,b])),1)
        self.assertEqual(shared_products([a,dict(b,quantity='2')]),[])
    def test_missing_chain_or_store_fails_entire_file(self):
        with self.assertRaises(ValueError):
            parse_prices(XML.replace(b'<StoreId>001</StoreId>',b''),'shufersal',datetime.now(timezone.utc))
    def test_listing_keeps_full_prices_only(self):
        html = '''<a href="https://x.blob.core.windows.net/a/PriceFull7290027600007-001-202610221200.gz?sig=secret&amp;x=1">x</a>'''
        name,url=listing('shufersal',html)
        self.assertTrue(name.startswith('PriceFull'))
        self.assertIn('&x=1',url)
        with self.assertRaises(ValueError): listing('carrefour','no files')

if __name__ == '__main__': unittest.main()
