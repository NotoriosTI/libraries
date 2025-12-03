from .api import OdooAPI
from env_manager import init_config, get_config
from models.partner_models import Partner


class OdooPartner(OdooAPI):
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

    def add_partner(
        self,
        name: str,
        email: str,
        supplier_rank: int = 0,
        customer_rank: int = 0,
    ) -> Partner:
        if not name:
            raise ValueError("Name required")
        if not email:
            raise ValueError("Email required")

        partner_id = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.partner",
            "create",
            [
                {
                    "name": name,
                    "email": email,
                    "supplier_rank": supplier_rank,
                    "customer_rank": customer_rank,
                }
            ],
        )
        created_partner = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.partner",
            "read",
            [partner_id],
            {"fields": ["id", "name", "email", "customer_rank", "supplier_rank"]},
        )

        return Partner(**created_partner[0])

    def get_partner_by_email(self, email) -> Partner:
        if not email:
            raise ValueError("Email required")

        partners = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.partner",
            "search_read",
            [[["email", "=ilike", email]]],
            {
                "fields": ["id", "name", "email", "customer_rank", "supplier_rank"],
                "limit": 1,
            },
        )
        if not partners:
            return None

        selected_partner = partners[0]

        try:
            partner_object = Partner(**selected_partner)
            return partner_object
        except Exception as e:
            print(f"Unknown error when parsing partner object: {e}")

    def get_partner_by_name(self, name) -> Partner:
        if not name:
            raise ValueError("Name required")

        partners = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.partner",
            "search_read",
            [[["name", "=ilike", name]]],
            {
                "fields": ["id", "name", "email", "customer_rank", "supplier_rank"],
                "limit": 1,
            },
        )
        if not partners:
            return None

        selected_partner = partners[0]

        try:
            partner_object = Partner(**selected_partner)
            return partner_object
        except Exception as e:
            print(f"Unknown error when parsing partner object: {e}")

    def is_customer(self, email):
        partner = self.get_partner_by_email(email)
        return bool(partner and partner.customer_rank > 0)

    def is_supplier(self, email):
        partner = self.get_partner_by_email(email)
        return bool(partner and partner.supplier_rank > 0)


if __name__ == "__main__":
    init_config("config/env_vars.yaml")
    partner = OdooPartner(
        db=get_config("ODOO_PROD_DB"),
        url=get_config("ODOO_PROD_URL"),
        username=get_config("ODOO_PROD_USERNAME"),
        password=get_config("ODOO_PROD_PASSWORD"),
    )

    print(partner.is_supplier("evergara@sabores.cl"))

    partner_data = partner.get_partner_by_email("evergara@sabores.cl")
    print(partner_data)

    ADD_PARTNER = False

    if ADD_PARTNER:
        print(partner.get_partner_by_email("basman176@gmail.com"))
        partner.add_partner("Bastian Ibañez", "basman176@gmail.com", 1, 0)
        print(partner.get_partner_by_email("basman176@gmail.com"))
