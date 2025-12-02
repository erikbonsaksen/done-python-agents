from typing import List, Dict, Any

from ..finago_config import FINAGO_CRM_URL, NS
from ..finago_soap import FinagoSoapClient
from ..finago_utils import v as _v


def _download_companies(
    client: FinagoSoapClient,
    changed_after: str,
) -> List[Dict[str, Any]]:
    """
    Mirror what CompanyService.searchCompanies does in JS, but in Python.
    Calls GetCompanies with a <ChangedAfter> filter.
    """
    if not FINAGO_CRM_URL:
        return []

    # Same handling as JS: "2024-01-01" → "2024-01-01T00:00:00"
    ds = changed_after if "T" in changed_after else f"{changed_after}T00:00:00"

    search_params = f"<ChangedAfter>{ds}</ChangedAfter>"

    props = [
        "CompanyId",
        "ExternalId",
        "CompanyName",
        "CompanyEmail",
        "CompanyPhone",
        "OrganizationNumber",
        "ChangedAfter",
    ]
    props_xml = "".join(f"<string>{p}</string>" for p in props)

    inner = f"""
<GetCompanies xmlns="{NS}">
  <searchParams>{search_params}</searchParams>
  <returnProperties>{props_xml}</returnProperties>
</GetCompanies>
"""

    doc = client.call("GetCompanies", inner)

    body = doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetCompaniesResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = resp.get("GetCompaniesResult") if isinstance(resp, dict) else None
    if isinstance(result, list):
        result = result[0]

    raw_companies = []
    if isinstance(result, dict):
        raw_companies = result.get("Company") or []

    if isinstance(raw_companies, dict):
        raw_companies = [raw_companies]

    companies: List[Dict[str, Any]] = []
    for c in raw_companies:
        companies.append(
            {
                "companyId": int(_v(c, "CompanyId") or _v(c, "Id") or 0),
                "companyName": (_v(c, "CompanyName") or _v(c, "Name") or ""),
                "organizationNo": (_v(c, "OrganizationNumber") or ""),
                "customerNumber": "",
                "email": (_v(c, "CompanyEmail") or _v(c, "Email") or ""),
                "phone": (_v(c, "CompanyPhone") or _v(c, "Phone") or ""),
                "dateChanged": (_v(c, "ChangedAfter") or _v(c, "ChangedDate") or ""),
            }
        )

    return companies


def download_companies(session_id: str, changed_after: str) -> List[Dict[str, Any]]:
    """
    Public API: creates a CRM SOAP client and returns normalized companies.
    """
    if not FINAGO_CRM_URL:
        print("FINAGO_CRM_URL not set – skipping company download.")
        return []

    client = FinagoSoapClient(FINAGO_CRM_URL)
    client.set_session(session_id)

    return _download_companies(client, changed_after)
