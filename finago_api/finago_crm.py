# finago_crm.py
from typing import List, Dict, Any, Tuple

from finago_config import FINAGO_CRM_URL, NS
from finago_soap import FinagoSoapClient


def _normalize_value(d: Dict[str, Any], key: str):
    val = d.get(key)
    if isinstance(val, list):
        val = val[0]
    return val


def download_companies_and_persons(
    session_id: str,
    changed_after: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Calls the 24SO Company (and later Person) SOAP services and returns:
      - companies: list of dicts for companies_sync
      - persons:   list of dicts for persons_sync
    """
    if not FINAGO_CRM_URL:
        print("FINAGO_CRM_URL not set – skipping CRM download.")
        return [], []

    crm_client = FinagoSoapClient(FINAGO_CRM_URL)
    crm_client.set_session(session_id)

    # Same date as in Next.js: "2024-01-01" -> "2024-01-01T00:00:00"
    changed_after_dt = f"{changed_after}T00:00:00"

    # 👉 IMPORTANT:
    # Use the EXACT same body and SOAPAction as in Next.js /api/tfso/download-companies.
    # The shape below is a template – tweak to match your working JS.
    companies_inner = f"""
      <GetCompanies xmlns="{NS}">
        <searchParams>
          <ChangedAfter>{changed_after_dt}</ChangedAfter>
        </searchParams>
        <returnProperties>
          <string>Id</string>
          <string>Name</string>
          <string>OrganizationNumber</string>
          <string>CustomerNumber</string>
          <string>DateChanged</string>
        </returnProperties>
      </GetCompanies>
    """

    # 🔹 Replace SOAPAction below with your working one from Next.js:
    companies_doc = crm_client.call(
        "GetCompanies",
        companies_inner,
    )

    body = companies_doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetCompaniesResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = None
    if isinstance(resp, dict):
        result = resp.get("GetCompaniesResult") or resp

    raw_companies = []
    if isinstance(result, dict):
        raw_companies = (
            result.get("Company") or
            result.get("CompanyInfo") or
            result.get("Companies") or
            []
        )

    if isinstance(raw_companies, dict):
        raw_companies = [raw_companies]

    companies: List[Dict[str, Any]] = []

    for c in raw_companies:
        companies.append(
            {
                "companyId": int(
                    _normalize_value(c, "CompanyId")
                    or _normalize_value(c, "Id")
                    or 0
                ),
                "companyName": _normalize_value(c, "Name") or "",
                "organizationNo": _normalize_value(c, "OrganizationNumber") or "",
                "customerNumber": _normalize_value(c, "CustomerNumber") or "",
                "email": _normalize_value(c, "Email") or "",
                "phone": _normalize_value(c, "Phone") or "",
                "dateChanged": _normalize_value(c, "DateChanged") or "",
            }
        )

    # PersonService is another endpoint; you can wire it up later and return persons.
    persons: List[Dict[str, Any]] = []

    return companies, persons
