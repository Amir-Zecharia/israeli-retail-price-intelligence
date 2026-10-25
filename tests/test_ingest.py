from copy import deepcopy
from pipeline.ingest import normalize


def test_normalize_rejects_invalid_and_conflicting_duplicates():
    product={'gtin':'00000072917329','quantity':'45','unit':'גרם'}
    row={'gtin':product['gtin'],'quantity':'45.00','unit':'גרם','price_ils':'4.50','product_name':'p'}
    rows,counts,issues=normalize([row,deepcopy(row),dict(row,price_ils='7'),dict(row,price_ils='NaN')], [product])
    assert rows==[]
    assert counts=={'received':4,'accepted':0,'rejected':3,'duplicate':1}
    assert issues


def test_normalize_preserves_decimal_and_missing_coverage():
    p={'gtin':'00000072917329','quantity':'45','unit':'גרם'}
    rows,counts,_=normalize([dict(p,price_ils='4.50',product_name='p')], [p])
    assert str(rows[0]['price_ils'])=='4.50'
    assert counts['accepted']==1
