# finago_api/endpoint/finago_products.py

from typing import List, Dict, Any

from ..finago_config import FINAGO_PRODUCT_URL, NS
from ..finago_soap import FinagoSoapClient
from ..finago_utils import v as _v

# Which product fields we want back
PRODUCT_RETURN_PROPS = [
    "Id",
    "No",
    "Name",
    "Description",
    "Price",
    "CostPrice",
    "IsActive",
    "Vat",
    "DateChanged",
]


def download_products(
    session_id: str,
    changed_after: str = "2000-01-01",
) -> List[Dict[str, Any]]:
    """
    Fetch products for use in AI analytics.

    Target table: products_sync
      productId, productNo, name, description,
      unitPrice, costPrice, isActive, vatCode, dateChanged
    """
    if not FINAGO_PRODUCT_URL:
        print("FINAGO_PRODUCT_URL not set – skipping products.")
        return []

    client = FinagoSoapClient(FINAGO_PRODUCT_URL)
    client.set_session(session_id)

    ds = changed_after if "T" in changed_after else f"{changed_after}T00:00:00"

    # ProductService expects ProductSearchParameters with DateChanged
    search_xml = f"<DateChanged>{ds}</DateChanged>"

    props_xml = "".join(f"<string>{p}</string>" for p in PRODUCT_RETURN_PROPS)

    inner = f"""
<GetProducts xmlns="{NS}">
  <searchParams>
    {search_xml}
  </searchParams>
  <returnProperties>
    {props_xml}
  </returnProperties>
</GetProducts>
""".strip()

    doc = client.call("GetProducts", inner)

    body = doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetProductsResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = resp.get("GetProductsResult") if isinstance(resp, dict) else None
    if isinstance(result, list):
        result = result[0]

    raw_items = []
    if isinstance(result, dict):
        # In WSDL the element is "Product"
        raw_items = result.get("Product") or result.get("ProductItem") or []

    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    products: List[Dict[str, Any]] = []

    for p in raw_items:
        # Safe float conversion
        def _to_float(val: Any) -> float:
            if val is None or val == "":
                return 0.0
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0

        products.append(
            {
                "productId": int(_v(p, "Id") or _v(p, "ProductId") or 0),
                "productNo": _v(p, "No") or _v(p, "ProductNo") or "",
                "name": _v(p, "Name") or _v(p, "ProductName") or "",
                "description": _v(p, "Description") or "",
                "unitPrice": _to_float(_v(p, "Price") or _v(p, "UnitPrice")),
                "costPrice": _to_float(_v(p, "CostPrice")),
                "isActive": 1
                if str(_v(p, "IsActive") or "true").lower() == "true"
                else 0,
                "vatCode": str(_v(p, "Vat") or _v(p, "VatCode") or ""),
                "dateChanged": _v(p, "DateChanged") or _v(p, "ChangedDate") or "",
            }
        )

    return products
