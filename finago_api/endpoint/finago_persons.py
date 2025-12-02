# finago_api/endpoint/finago_persons.py

from typing import List, Dict, Any, Optional

from ..finago_config import FINAGO_PERSON_URL, NS
from ..finago_soap import FinagoSoapClient
from ..finago_utils import v as _v


def _extract_email(p: Dict[str, Any]) -> Optional[str]:
    """
    Extract primary email from:
      PersonItem.EmailAddresses.EmailAddress[].Value
    Fallback to flat PersonItem.Email.
    """
    email_container = p.get("EmailAddresses")
    if isinstance(email_container, list):
        email_container = email_container[0]

    if isinstance(email_container, dict):
        emails = email_container.get("EmailAddress") or []
        if isinstance(emails, dict):
            emails = [emails]

        if isinstance(emails, list) and emails:
            # Prefer Type == 'Primary' if present
            primary = None
            for e in emails:
                t = _v(e, "Type") or ""
                if t.lower() == "primary":
                    primary = e
                    break
            chosen = primary or emails[0]
            return _v(chosen, "Value")

    # Fallback to flat Email field
    return _v(p, "Email")


def _extract_phone(p: Dict[str, Any]) -> str:
    """
    Extracts a phone number, preferring mobile if present.
    Looks in PhoneNumbers.PhoneNumber[].Value, then flat Phone/Mobile.
    """
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
            # Look for Type == 'Mobile'
            mob_row = None
            for ph in phones:
                t = _v(ph, "Type") or ""
                if t.lower() == "mobile":
                    mob_row = ph
                    break

            if mob_row:
                mobile = _v(mob_row, "Value")

            # Fallback to first phone if no explicit mobile
            if not mobile:
                phone_val = _v(phones[0], "Value")
                phone = phone_val or phone

    if not phone:
        phone = _v(p, "Phone")
    if not mobile:
        mobile = _v(p, "Mobile")

    return mobile or phone or ""


def _extract_company_id_from_relations(p: Dict[str, Any]) -> Optional[int]:
    """
    Extracts company/customer relation from PersonItem.RelationData[].

    This is what shows up as “Firmakobling” in the 24SO/Finago UI.

    XML shape (simplified):

      <PersonItem>
        ...
        <RelationData>
          <RelationData>
            <CustomerId>1234</CustomerId>
            <Title>Boss</Title>
            ...
          </RelationData>
          <!-- possibly more RelationData elements -->
        </RelationData>
      </PersonItem>

    For now we just pick the first RelationData.CustomerId.
    """
    rel_container = p.get("RelationData")
    if isinstance(rel_container, list):
        rel_container = rel_container[0]

    if not isinstance(rel_container, dict):
        return None

    rels = rel_container.get("RelationData") or []
    if isinstance(rels, dict):
        rels = [rels]

    if not rels:
        return None

    first_rel = rels[0]
    cid = _v(first_rel, "CustomerId")

    try:
        return int(cid) if cid is not None else None
    except (TypeError, ValueError):
        return None


def download_persons(
    session_id: str,
    changed_after: str = "2000-01-01",
) -> List[Dict[str, Any]]:
    """
    Rough Python port of PersonService.getPersonsDetailed + mapPersonItem.

    We only populate fields that exist in your persons_sync table:
      personId, companyId, customerId, name, email, phone, role, dateChanged

    - We call GetPersonsDetailed with <ChangedAfter> and <GetRelationData>true</GetRelationData>
    - companyId / customerId are taken from:
        1) RelationData[].CustomerId  (Firmakobling in the UI)
        2) PersonItem.CustomerId      (for consumer customers) as fallback
    """
    if not FINAGO_PERSON_URL:
        print("FINAGO_PERSON_URL not set – skipping persons.")
        return []

    person_client = FinagoSoapClient(FINAGO_PERSON_URL)
    person_client.set_session(session_id)

    ds = changed_after if "T" in changed_after else f"{changed_after}T00:00:00"

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

    raw_persons: Any = []
    if isinstance(result, dict):
        raw_persons = result.get("PersonItem") or []

    if isinstance(raw_persons, dict):
        raw_persons = [raw_persons]

    persons: List[Dict[str, Any]] = []

    for p in raw_persons:
        # --- Name ---
        first_name = _v(p, "FirstName")
        last_name = _v(p, "LastName")
        full_name = _v(p, "FullName")
        if not full_name:
            full_name = " ".join([x for x in [first_name, last_name] if x]).strip()

        # --- Email & phone ---
        email = _extract_email(p)
        phone_final = _extract_phone(p)

        # --- Company / customer relation ---
        # 1) Preferred: firmakobling via RelationData
        company_id = _extract_company_id_from_relations(p)

        # 2) Fallback: PersonItem.CustomerId (used for consumer customers)
        if company_id is None:
            try:
                company_id = int(_v(p, "CustomerId") or 0) or None
            except (TypeError, ValueError):
                company_id = None

        try:
            person_id = int(_v(p, "Id") or 0)
        except (TypeError, ValueError):
            person_id = 0

        persons.append(
            {
                "personId": person_id,
                "companyId": company_id,
                "customerId": company_id,  # keep same for now; can be split later if needed
                "name": full_name or None,
                "email": email or None,
                "phone": phone_final or None,
                "role": _v(p, "WorkPosition") or _v(p, "Role") or None,
                # PersonService in JS doesn't really surface a proper DateChanged,
                # so we keep it empty / None for now.
                "dateChanged": None,
            }
        )

    return persons
