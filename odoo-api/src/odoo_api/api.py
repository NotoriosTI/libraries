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


    def _authenticate(self):
        self.common = xc.ServerProxy(f'{self.url}/xmlrpc/2/common')
        self.uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not self.uid:
            raise ValueError("Error de autenticación en Odoo API")

        print("url", self.url)
        print("common", self.common)
        print("uid", self.uid)
        print("db", self.db)
        print("user", self.username)
        print("pass", self.password)
    
    def _create_model(self):
        self.models = xc.ServerProxy(f'{self.url}/xmlrpc/2/object')

    def __enter__(self):
        # Si necesitas lógica extra al entrar al contexto, agrégala aquí
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass
    
    def get_fields(self, table):
        fields = self.models.execute_kw(self.db, self.uid, self.password, table, 'fields_get', [])
        df_fields = pd.DataFrame.from_dict(fields, orient='index')
        return df_fields