from .api import OdooAPI
from env_manager import init_config, get_config
from models.partner_models import Partner


class OdooPartner(OdooAPI):
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

    def _get_partner_by_email(self, email) -> Partner:
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
        selected_partner = partners[0]

        try:
            partner_object = Partner(**selected_partner)
            return partner_object
        except Exception as e:
            print(f"Unknown error when parsing partner object: {e}")

    def is_customer(self, email):
        partner = self._get_partner_by_email(email)
        return bool(partner and partner.customer_rank > 0)

    def is_supplier(self, email):
        partner = self._get_partner_by_email(email)
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

    partner_data = partner._get_partner_by_email("evergara@sabores.cl")
    print(partner_data)
