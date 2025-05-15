import xmlrpc.client as xc
import pandas as pd
from decouple import Config, RepositoryEnv

class OdooAPI:
    def __init__(self, database='productive'):
        # Validate database parameter
        if database not in ['productive', 'test']:
            raise ValueError("Error: La base de datos debe ser 'productive' o 'test'")
            
        base_path = '/home/snparada/Spacionatural/Libraries/odoo_lib/creds/'
        env_path = base_path + '.env'
        
        config = Config(RepositoryEnv(env_path))
        
        # Use different environment variable names depending on database type
        prefix = '' if database == 'productive' else 'TEST_'
        
        self.url = config(f'ODOO_{prefix}URL')
        self.db = config(f'ODOO_{prefix}DB')
        self.username = config(f'ODOO_{prefix}USERNAME')
        self.password = config(f'ODOO_{prefix}PASSWORD')
        self.uid = self._authenticate()
        self.models = self._create_model()

    def _authenticate(self):
        common = xc.ServerProxy(f'{self.url}/xmlrpc/2/common')
        uid = common.authenticate(self.db, self.username, self.password, {})
        return uid

    def _create_model(self):
        return xc.ServerProxy(f'{self.url}/xmlrpc/2/object')

    def get_fields(self, table):
        fields = self.models.execute_kw(self.db, self.uid, self.password, table, 'fields_get', [])
        df_fields = pd.DataFrame.from_dict(fields, orient='index')
        return df_fields