# finago_crm.py

from typing import List, Dict, Any, Tuple

from finago_config import FINAGO_CRM_URL, FINAGO_PERSON_URL, NS
from finago_soap import FinagoSoapClient


def _v(d: Dict[str, Any], key: str):
    """Normalize values coming from xmltodict (may be lists)."""
    val = d.get(key)
    if isinstance(val, list):
        val = val[0]
    return val


# -----------------------------
# COMPANIES (GetCompanies)
# -----------------------------
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

    # Build <searchParams> like searchCompanies
    search_params = f"<ChangedAfter>{ds}</ChangedAfter>"

    # You can tune returnProperties; these are close to the JS route:
    #   'CompanyId','ExternalId','CompanyName','CompanyEmail','CompanyPhone',
    #   'OrganizationNumber','ChangedAfter'
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
                # map into your finago_db.companies_sync schema
                "companyId": int(_v(c, "CompanyId") or _v(c, "Id") or 0),
                "companyName": (_v(c, "CompanyName") or _v(c, "Name") or ""),
                "organizationNo": (_v(c, "OrganizationNumber") or ""),
                # you don't have externalId in schema, so we skip it
                "customerNumber": "",  # not returned by this query, keep empty
                "email": (_v(c, "CompanyEmail") or _v(c, "Email") or ""),
                "phone": (_v(c, "CompanyPhone") or _v(c, "Phone") or ""),
                "dateChanged": (_v(c, "ChangedAfter") or _v(c, "ChangedDate") or ""),
            }
        )

    return companies


# -----------------------------
# PERSONS (GetPersonsDetailed)
# -----------------------------
def _download_persons(
    session_id: str,
    changed_after: str,
) -> List[Dict[str, Any]]:
    """
    Rough Python port of PersonService.getPersonsDetailed + mapPersonItem.

    We only populate fields that exist in your persons_sync table:
      personId, companyId, customerId, name, email, phone, role, dateChanged
    """
    if not FINAGO_PERSON_URL:
        return []

    person_client = FinagoSoapClient(FINAGO_PERSON_URL)
    person_client.set_session(session_id)

    ds = changed_after if "T" in changed_after else f"{changed_after}T00:00:00"

    # Build personSearch like PersonService.buildSearchXml({ changedAfter, getRelationData })
    person_search = f"""
<ChangedAfter>{ds}</ChangedAfter>
<GetRelationData>true</GetRelationData>
""".strip()

    inner = f"""
<GetPersonsDetailed xmlns="{NS}">
  <personSearch>
    {person_search}
  </personSearch>
</GetPersonsDetailed>
"""

    doc = person_client.call("GetPersonsDetailed", inner)

    body = doc.get("soap:Envelope", {}).get("soap:Body", {})
    resp = body.get("GetPersonsDetailedResponse")
    if isinstance(resp, list):
        resp = resp[0]

    result = resp.get("GetPersonsDetailedResult") if isinstance(resp, dict) else None
    if isinstance(result, list):
        result = result[0]

    raw_persons = []
    if isinstance(result, dict):
        raw_persons = result.get("PersonItem") or []

    if isinstance(raw_persons, dict):
        raw_persons = [raw_persons]

    persons: List[Dict[str, Any]] = []

    for p in raw_persons:
        # Names
        first_name = _v(p, "FirstName")
        last_name = _v(p, "LastName")
        full_name = _v(p, "FullName")
        if not full_name:
            full_name = " ".join([x for x in [first_name, last_name] if x]).strip()

        # Email: try EmailAddresses.EmailAddress[*].Value → primary or first
        email = None
        email_container = p.get("EmailAddresses")
        if isinstance(email_container, list):
            email_container = email_container[0]
        if isinstance(email_container, dict):
            emails = email_container.get("EmailAddress") or []
            if isinstance(emails, dict):
                emails = [emails]
            if isinstance(emails, list) and emails:
                # try primary
                primary = None
                for e in emails:
                    t = _v(e, "Type") or ""
                    if t.lower() == "primary":
                        primary = e
                        break
                chosen = primary or emails[0]
                email = _v(chosen, "Value")

        if not email:
            # fallback to flat Email field if present
            email = _v(p, "Email")

        # Phone & mobile from PhoneNumbers.PhoneNumber
        phone = None
        mobile = None
        phone_container = p.get("PhoneNumbers")
        if isinstance(phone_container, list):
            phone_container = phone_container[0]
        if isinstance(phone_container, dict):
            phones = phone_container.get("PhoneNumber") or []
            if isinstance(phones, dict):
                phones = [phones]
            if isinstance(phones, list) and phones:
                # find a 'mobile' row
                mob_row = None
                for ph in phones:
                    t = _v(ph, "Type") or ""
                    if t.lower() == "mobile":
                        mob_row = ph
                        break
                if mob_row:
                    mobile = _v(mob_row, "Value")
                # fallback to first phone if no mobile
                if not mobile:
                    phone_val = _v(phones[0], "Value")
                    phone = phone_val or phone
        if not phone:
            phone = _v(p, "Phone")
        if not mobile:
            mobile = _v(p, "Mobile")

        # pick mobile first for "phone"
        phone_final = mobile or phone or ""

        persons.append(
            {
                "personId": int(_v(p, "Id") or 0),
                # in 24SO person → company is "CustomerId"
                "companyId": int(_v(p, "CustomerId") or 0) or None,
                "customerId": int(_v(p, "CustomerId") or 0) or None,
                "name": full_name or None,
                "email": email or None,
                "phone": phone_final or None,
                "role": _v(p, "WorkPosition") or _v(p, "Role") or None,
                # PersonService in JS doesn't really surface DateChanged,
                # so we keep it empty / None for now.
                "dateChanged": None,
            }
        )

    return persons


# -----------------------------
# PUBLIC API
# -----------------------------
def download_companies_and_persons(
    session_id: str,
    changed_after: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Used by finago_sync_cli.py.

    - Companies: GetCompanies with <ChangedAfter> filter
    - Persons:   GetPersonsDetailed with <ChangedAfter> filter

    To fetch *everything* once, call with changed_after="2000-01-01"
    in your CLI.
    """
    if not FINAGO_CRM_URL:
        print("FINAGO_CRM_URL not set – skipping CRM download.")
        return [], []

    crm_client = FinagoSoapClient(FINAGO_CRM_URL)
    crm_client.set_session(session_id)

    # --- COMPANIES ---
    companies = _download_companies(crm_client, changed_after)
    if not companies:
        print("  - No companies returned from SOAP (check changed_after).")

    # --- PERSONS ---
    persons: List[Dict[str, Any]] = []
    if FINAGO_PERSON_URL:
        try:
            persons = _download_persons(session_id, "2000-01-01")  # same as JS
        except Exception as e:
            print(f"  - Warning: failed to download persons: {e}")
    else:
        print("  - FINAGO_PERSON_URL not set – skipping persons.")

    return companies, persons
