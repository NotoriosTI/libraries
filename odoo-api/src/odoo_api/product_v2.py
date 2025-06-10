import warnings
from odoo_api.product import *

warnings.warn(
"""
product_v2.py ahora es product.py
Asegurate de arreglar este import ya que en el futuro
product_v2.py dejara de existir.
""",
DeprecationWarning,
stacklevel=2
)
