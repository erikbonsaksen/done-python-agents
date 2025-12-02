from finago_config import (
    FINAGO_APP_ID,
    FINAGO_USERNAME,
    FINAGO_PASSWORD,
    FINAGO_AUTH_URL,
    require_core_config,
)
from finago_soap import FinagoSoapClient
from finago_auth import AuthService
from finago_crm import download_companies_and_persons
from finago_invoices import download_invoices

from finago_db import (
    get_connection,
    init_schema,
    upsert_companies,
    upsert_persons,
    upsert_invoices,
)


def main() -> None:
    require_core_config()

    print("=== Finago SOAP CLI ===")
    print(f"Auth URL: {FINAGO_AUTH_URL}")
    client = FinagoSoapClient(FINAGO_AUTH_URL)
    auth = AuthService(client)

    # 1) Login
    print("\n1) Logging in with integration user...")
    session_id = auth.login(FINAGO_APP_ID, FINAGO_USERNAME, FINAGO_PASSWORD)
    print(f"SessionId: {session_id}")

    # 2) Get identities
    print("\n2) Fetching identities (clients)...")
    identities = auth.get_identities()
    if not identities:
        print("No identities found for this user.")
        return

    print("\nAvailable identities:")
    for idx, ident in enumerate(identities, start=1):
        label = ident.name or "(uten navn)"
        print(f"{idx:2d}) {label} – user: {ident.user_name} (IdentityId: {ident.id})")

    # 3) Choose identity (like select + Bekreft klient)
    while True:
        choice = input("\nSelect identity number to use: ").strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(identities):
                chosen = identities[idx - 1]
                break
            else:
                print(f"Please choose a number between 1 and {len(identities)}")
        except ValueError:
            print("Please enter a valid number.")

    print(f"\n3) Setting identity: {chosen.id} ({chosen.name})...")
    auth.set_identity_by_id(chosen.id or "")
    print("Identity set – same as clicking 'Bekreft klient' in the Next.js UI.")

    # 4) Download + persist
    print("\n4) Downloading CRM and invoice data into tfso-data.db ...")
    changed_after = "2000-01-01" 

    conn = get_connection()
    init_schema(conn)

    # CRM
    companies, persons = download_companies_and_persons(session_id, changed_after)

    if companies:
        n_comp = upsert_companies(conn, companies)
        print(f"  - Upserted {n_comp} companies into companies_sync")
    else:
        print("  - No companies returned from SOAP")

    if persons:
        n_pers = upsert_persons(conn, persons)
        print(f"  - Upserted {n_pers} persons into persons_sync")
    else:
        print("  - No persons returned from SOAP")

    # Invoices
    try:
        invoices = download_invoices(session_id, changed_after)
        if invoices:
            n_inv = upsert_invoices(conn, invoices)
            print(f"  - Upserted {n_inv} invoices into invoices_sync")
        else:
            print("  - No invoices returned from SOAP")
    except Exception as e:
        print("  - Failed to download invoices from SOAP:", e)

    conn.close()

    print("\nDone ✅ tfso-data.db is now populated.")
    print("Open the Streamlit agent again to query the fresh data.")


if __name__ == "__main__":
    main()
