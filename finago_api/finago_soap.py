from dataclasses import dataclass
from typing import Dict, Any, Optional, List

import requests
import xmltodict

from .finago_config import NS


def soap_envelope(inner_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
{inner_xml}
  </soap:Body>
</soap:Envelope>
"""


@dataclass
class Identity:
    id: str
    name: Optional[str]
    client_id: Optional[str]
    user_name: Optional[str]


class FinagoSoapClient:
    def __init__(self, base_url: str, namespace: str = NS):
        self.base_url = base_url
        self.ns = namespace
        self.session = requests.Session()
        self.session_id: Optional[str] = None

    def set_session(self, session_id: str) -> None:
        self.session_id = session_id
        # Same cookie strategy as Next.js SoapClient
        self.session.cookies.set(
            "ASP.NET_SessionId",
            session_id,
            domain=".24sevenoffice.com",
        )

    def call(self, action_name: str, inner_xml: str) -> Dict[str, Any]:
        """
        action_name: e.g. "Login", "GetIdentities", "GetCompanies"
        -> SOAPAction = `${NS}/${action_name}` (no extra quotes)
        """
        xml = soap_envelope(inner_xml)

        soap_action = f"{self.ns}/{action_name}"  # EXACTLY like Next.js
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": soap_action,  # ❌ DO NOT WRAP IN QUOTES
        }

        resp = self.session.post(
            self.base_url,
            data=xml.encode("utf-8"),
            headers=headers,
            timeout=30,
        )

        # Debug on non-2xx
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            print("\n--- SOAP HTTP ERROR ---------------------------------")
            print(f"URL: {self.base_url}")
            print(f"SOAPAction: {headers['SOAPAction']}")
            print("Request body:")
            print(xml)
            print("\nResponse body:")
            print(resp.text)
            print("-----------------------------------------------------\n")
            raise

        return xmltodict.parse(resp.text)
