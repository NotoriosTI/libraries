import xmlrpc.client as xc
import pandas as pd
from decouple import Config, RepositoryEnv
import os

class OdooAPI:
    def __init__(self, database='test', dotenv_path=None):
        # Validate database parameter
        if database not in ['productive', 'test']:
            raise ValueError("Error: La base de datos debe ser 'productive' o 'test'")
        
        if dotenv_path is None:
            base_path = '/home/admin_/langgraph_projects/spacio_natural/juan/'
            env_path = base_path + '.env'
        else:
            env_path = dotenv_path
            base_path = os.path.dirname(env_path)
        
        config = Config(RepositoryEnv(env_path))
        
        # Use different environment variable names depending on database type
        prefix = '' if database == 'productive' else 'TEST_'
        
        self.url = config(f'ODOO_{prefix}URL')
        self.db = config(f'ODOO_{prefix}DB')
        self.username = config(f'ODOO_{prefix}USERNAME')
        self.password = config(f'ODOO_{prefix}PASSWORD')
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