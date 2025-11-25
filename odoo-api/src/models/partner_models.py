from pydantic import BaseModel


class Partner(BaseModel):
    id: int
    name: str
    email: str
    customer_rank: int
    supplier_rank: int
