from typing import Optional
from pydantic import BaseModel


class Partner(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    vat: Optional[str] = None
    customer_rank: int
    supplier_rank: int
