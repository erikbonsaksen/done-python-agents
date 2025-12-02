# finago_auth.py
from typing import List, Dict, Any

from .finago_config import NS
from .finago_soap import FinagoSoapClient, Identity


class AuthService:
    """
    Python port of Next.js AuthService:
      - login()
      - get_identities()
      - set_identity_by_id()
    """

    def __init__(self, client: FinagoSoapClient):
        self.client = client

    def login(self, application_id: str, username: str, password: str) -> str:
        inner = f"""
          <Login xmlns="{NS}">
            <credential>
              <ApplicationId>{application_id}</ApplicationId>
              <Username>{username}</Username>
              <Password>{password}</Password>
            </credential>
          </Login>
        """
        doc = self.client.call("Login", inner)

        body = doc.get("soap:Envelope", {}).get("soap:Body", {})

        login_resp = body.get("LoginResponse")
        if isinstance(login_resp, list):
            login_resp = login_resp[0]

        login_result = None
        if isinstance(login_resp, dict):
            login_result = login_resp.get("LoginResult")

        if isinstance(login_result, list):
            login_result = login_result[0]

        if not login_result:
            raise RuntimeError("Login ok, but missing LoginResult / sessionId")

        session_id = str(login_result).strip()
        if not self.client.session_id:
            self.client.set_session(session_id)

        return session_id

    def get_identities(self) -> List[Identity]:
        inner = f'<GetIdentities xmlns="{NS}" />'
        doc = self.client.call("GetIdentities", inner)

        body: Dict[str, Any] = doc.get("soap:Envelope", {}).get("soap:Body", {})
        resp = body.get("GetIdentitiesResponse")
        if isinstance(resp, list):
            resp = resp[0]

        result = None
        if isinstance(resp, dict):
            result = resp.get("GetIdentitiesResult")

        if isinstance(result, list):
            result = result[0]

        raw_identities = []
        if isinstance(result, dict):
            raw_identities = result.get("Identity") or []

        if isinstance(raw_identities, dict):
            raw_identities = [raw_identities]

        identities: List[Identity] = []

        for i in raw_identities:
            ident_id_val = i.get("Id")
            if isinstance(ident_id_val, list):
                ident_id_val = ident_id_val[0]

            client = i.get("Client") or {}
            if isinstance(client, list):
                client = client[0]

            user = i.get("User") or {}
            if isinstance(user, list):
                user = user[0]

            client_id = None
            client_name = None
            user_name = None

            if isinstance(client, dict):
                cid = client.get("Id")
                cname = client.get("Name")
                if isinstance(cid, list):
                    cid = cid[0]
                if isinstance(cname, list):
                    cname = cname[0]
                client_id = cid
                client_name = cname

            if isinstance(user, dict):
                uname = user.get("Name")
                if isinstance(uname, list):
                    uname = uname[0]
                user_name = uname

            identities.append(
                Identity(
                    id=str(ident_id_val) if ident_id_val is not None else None,
                    name=client_name,
                    client_id=client_id,
                    user_name=user_name,
                )
            )

        return identities

    def set_identity_by_id(self, identity_id: str) -> bool:
        inner = f"""
          <SetIdentityById xmlns="{NS}">
            <identityId>{identity_id}</identityId>
          </SetIdentityById>
        """
        self.client.call("SetIdentityById", inner)
        return True
