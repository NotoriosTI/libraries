import xmlrpc.client as xc
import pandas as pd

class OdooAPI:
    def __init__(
            self,
            db=None,
            url=None,
            username=None,
            password=None,
    ):
        # Validate parameters
        if not url:
            raise ValueError("Error: url es requerido")
        if not username:
            raise ValueError("Error: username es requerido")
        if not password:
            raise ValueError("Error: password es requerido")
        if not db:
            raise ValueError("Error: db es requerido")
        
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.common = None
        self.uid = None
        self.models = None

        self._authenticate()
        self._create_model()

        if self.uid:
            print("-- Authentication complete --")


    def _authenticate(self):
        self.common = xc.ServerProxy(f'{self.url}/xmlrpc/2/common')
        self.uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not self.uid:
            raise ValueError("Error de autenticación en Odoo API")

    def _create_model(self):
        self.models = xc.ServerProxy(f'{self.url}/xmlrpc/2/object')

    def __enter__(self):
        # Si necesitas lógica extra al entrar al contexto, agrégala aquí
        return self

    def __exit__(self, exc_type, exc_value, traceback):
    # This method ensures network resources are cleaned up safely.
    # The try...except blocks prevent any errors during cleanup
    # from crashing the application or masking the tool's real output.
        try:
            # Note: The exact way to close the connection depends on the library.
            # We assume the ServerProxy object is stored in self.models and self.common.
            # Often, the underlying transport needs to be closed. Since we cannot be
            # certain of the internal structure, we check for a 'close' method.
            if hasattr(self, 'models') and hasattr(self.models, 'close'):
                self.models.close()
        except Exception as e:
            pass
    
        try:
            # The typo from before is also fixed here.
            if hasattr(self, 'common') and hasattr(self.common, 'close'):
                self.common.close()
        except Exception as e:
            pass
    
    def get_fields(self, table):
        fields = self.models.execute_kw(self.db, self.uid, self.password, table, 'fields_get', [])
        df_fields = pd.DataFrame.from_dict(fields, orient='index')
        return df_fields