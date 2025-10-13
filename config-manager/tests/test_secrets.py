from config_manager.common import OdooProductionSecret
from config_manager.emilia import EmiliaDBSecret
from config_manager.emma import ChatwootSecret
from config_manager.juan import JuanDBSecret

if __name__ == "__main__":
    juandb_secrets = JuanDBSecret()
    # odoo_secrets = OdooProductionSecret()
    # emiliadb_secrets = EmiliaDBSecret()
    # chatwoot_secrets = ChatwootSecret()

    print(f"{juandb_secrets.host = }")
    print(f"{juandb_secrets.name = }")
    print(f"{juandb_secrets.username = }")
    print(f"{juandb_secrets.password = }")
    print(f"{juandb_secrets.port = }")
