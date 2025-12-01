# finago_soap.py
import textwrap
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests
import xmltodict

from finago_config import NS


def soap_envelope(inner_xml: str) -> str:
    """Wrap inner XML in a SOAP 1.1 envelope."""
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                       xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            {inner_xml}
          </soap:Body>
        </soap:Envelope>
    """)


@dataclass
class Identity:
    id: Optional[str]
    name: Optional[str]
    client_id: Optional[str]
    user_name: Optional[str]


class FinagoSoapClient:
    """
    Minimal SOAP client (Python port of your Next.js SoapClient).
    Keeps a requests.Session and stores ASP.NET_SessionId as a cookie.
    """

    def __init__(self, base_url: str, namespace: str = NS):
        self.base_url = base_url
        self.ns = namespace
        self.session = requests.Session()
        self.session_id: Optional[str] = None

    def set_session(self, session_id: str) -> None:
        self.session_id = session_id
        # Domain matches 24SO / Finago (.24sevenoffice.com)
        self.session.cookies.set(
            "ASP.NET_SessionId",
            session_id,
            domain=".24sevenoffice.com",
        )

    def call(
        self,
        action_name: str,
        inner_xml: str,
        full_action: bool = False,
    ) -> Dict[str, Any]:
        xml = soap_envelope(inner_xml)

        if full_action:
            soap_action = action_name              # use as-is
        else:
            soap_action = f"{self.ns}/{action_name}"  # default: NS + "/Name"

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": soap_action,
        }

        resp = self.session.post(
            self.base_url,
            data=xml.encode("utf-8"),
            headers=headers,
            timeout=30,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError:
            # Helpful debug output if Finago returns 400 / SOAP Fault
            print("\n--- SOAP HTTP ERROR ---------------------------------")
            print(f"URL: {self.base_url}")
            print(f"SOAPAction: {soap_action}")
            print("Request body:")
            print(xml)
            print("Response body:")
            print(resp.text)
            print("-----------------------------------------------------\n")
            raise

        return xmltodict.parse(resp.text)
