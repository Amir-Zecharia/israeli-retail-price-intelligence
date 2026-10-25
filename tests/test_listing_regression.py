import unittest
from datetime import datetime, timezone
from pipeline.extract.official import listing, parse_prices


class CarrefourListingRegression(unittest.TestCase):
    def test_shufersal_also_publishes_five_group_filenames(self):
        name = 'PriceFull7290027600007-001-001-20261023-043100.gz'
        html = '<a href="https://example.blob.core.windows.net/' + name + '?sig=fixture">file</a>'
        self.assertEqual(listing('shufersal', html)[0], name)

    def test_carrefour_timestamp_and_manufacturer_field_names(self):
        xml = b'''<root><ChainID>7290055700007</ChainID><StoreID>134</StoreID><Items><Item>
        <PriceUpdateTime>2026-10-23T10:00:00.000</PriceUpdateTime><ItemCode>7290000000008</ItemCode>
        <ItemName>Fixture</ItemName><ItemPrice>3.40</ItemPrice><ManufactureName>Fixture manufacturer</ManufactureName>
        <ItemType>1</ItemType><bIsWeighted>0</bIsWeighted></Item></Items></root>'''
        rows, rejected = parse_prices(xml, 'carrefour', datetime.now(timezone.utc))
        self.assertEqual(rejected, 0)
        self.assertEqual(rows[0]['source_updated_at'], '2026-10-23T07:00:00+00:00')
        self.assertEqual(rows[0]['manufacturer'], 'Fixture manufacturer')

    def test_actual_five_group_full_price_filename_and_latest_order(self):
        html = """const path = '20261023'; const files = [
        {"name":"PriceFull7290055700007-001-004-20261023-080001.gz"},
        {"name":"PriceFull7290055700007-001-005-20261023-070001.gz"},
        {"name":"Price7290055700007-001-004-20261023-090001.gz"}
        ];"""
        name, url = listing('carrefour', html)
        self.assertEqual(name, 'PriceFull7290055700007-001-004-20261023-080001.gz')
        self.assertEqual(url, 'https://prices.carrefour.co.il/20261023/' + name)

    def test_other_file_types_are_not_accepted(self):
        html = """const path = '20261023'; const files = [
        {"name":"PromoFull7290055700007-001-004-20261023-080001.gz"}
        ];"""
        with self.assertRaises(ValueError):
            listing('carrefour', html)

if __name__ == '__main__':
    unittest.main()
