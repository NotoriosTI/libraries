from config_manager.common import OdooProductionSecret
from config_manager.emilia import EmiliaDBSecret
from config_manager.emma import ChatwootSecret
from config_manager.juan import JuanDBSecret

if __name__ == "__main__":
    odoo_secrets = OdooProductionSecret()
    emiliadb_secrets = EmiliaDBSecret()
    juandb_secrets = JuanDBSecret()
    chatwoot_secrets = ChatwootSecret()

    print(f"{odoo_secrets.db = }")
    print(f"{emiliadb_secrets.host = }")
    print(f"{juandb_secrets.host = }")
    print(f"{chatwoot_secrets.account_id = }")
