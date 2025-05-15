# test_crm.py
import sys
sys.path.append('/home/snparada/Spacionatural/Libraries/')
from odoo_lib.crm import OdooCRM

crm = OdooCRM()
print(crm.read_stages())