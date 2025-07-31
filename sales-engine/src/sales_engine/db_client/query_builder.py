"""
Query Builder Simplificado para Sales Engine

Un constructor de consultas SQL simple y directo.
"""

from datetime import date
from typing import List, Optional, Tuple, Any


class QueryBuilder:
    """Constructor de consultas SQL simplificado."""
    
    def __init__(self):
        self._select_fields = []
        self._where_conditions = []
        self._params = []
        self._group_by_fields = []
        self._order_by_clause = ""
        self._limit_value = None
    
    def select(self, *fields: str) -> 'QueryBuilder':
        """Agregar campos al SELECT."""
        self._select_fields.extend(fields)
        return self
    
    def where(self, field: str, operator: str, value: Any) -> 'QueryBuilder':
        """Agregar condición WHERE."""
        self._where_conditions.append(f"{field} {operator} %s")
        self._params.append(value)
        return self
    
    def where_date_range(self, field: str, start_date: Optional[date] = None, end_date: Optional[date] = None) -> 'QueryBuilder':
        """Agregar filtro de rango de fechas."""
        if start_date:
            self.where(field, '>=', start_date)
        if end_date:
            self.where(field, '<=', end_date)
        return self
    
    def where_in(self, field: str, values: List[Any]) -> 'QueryBuilder':
        """Agregar condición WHERE IN."""
        if values:
            placeholders = ','.join(['%s'] * len(values))
            self._where_conditions.append(f"{field} IN ({placeholders})")
            self._params.extend(values)
        return self
    
    def group_by(self, *fields: str) -> 'QueryBuilder':
        """Agregar campos al GROUP BY."""
        self._group_by_fields.extend(fields)
        return self
    
    def order_by(self, field: str, direction: str = 'ASC') -> 'QueryBuilder':
        """Agregar ORDER BY."""
        self._order_by_clause = f"ORDER BY {field} {direction}"
        return self
    
    def order_by_desc(self, field: str) -> 'QueryBuilder':
        """Agregar ORDER BY DESC."""
        return self.order_by(field, 'DESC')
    
    def limit(self, count: int) -> 'QueryBuilder':
        """Agregar LIMIT."""
        self._limit_value = count
        return self
    
    def build(self) -> Tuple[str, List[Any]]:
        """Construir la consulta SQL final."""
        # SELECT
        if not self._select_fields:
            self._select_fields = ['*']
        
        select_clause = f"SELECT {', '.join(self._select_fields)}"
        
        # FROM (tabla fija)
        from_clause = "FROM sales_items"
        
        # WHERE
        where_clause = ""
        if self._where_conditions:
            where_clause = f"WHERE {' AND '.join(self._where_conditions)}"
        
        # GROUP BY
        group_by_clause = ""
        if self._group_by_fields:
            group_by_clause = f"GROUP BY {', '.join(self._group_by_fields)}"
        
        # ORDER BY
        order_by_clause = self._order_by_clause
        
        # LIMIT
        limit_clause = ""
        if self._limit_value:
            limit_clause = f"LIMIT {self._limit_value}"
        
        # Construir query completa
        query_parts = [select_clause, from_clause, where_clause, group_by_clause, order_by_clause, limit_clause]
        query = ' '.join(part for part in query_parts if part)
        
        return query, self._params.copy()


# === FUNCIONES DE CONVENIENCIA ===

def sales_by_date_range(start_date: Optional[date] = None, end_date: Optional[date] = None) -> QueryBuilder:
    """Consulta de ventas por rango de fechas."""
    return QueryBuilder().select('*').where_date_range('issueddate', start_date, end_date).order_by_desc('issueddate')


def sales_by_customer(customer_ids: List[int]) -> QueryBuilder:
    """Consulta de ventas por cliente(s)."""
    return QueryBuilder().select('*').where_in('customer_customerid', customer_ids).order_by_desc('issueddate')


def sales_by_product(product_skus: List[str]) -> QueryBuilder:
    """Consulta de ventas por producto(s)."""
    return QueryBuilder().select('*').where_in('items_product_sku', product_skus).order_by_desc('issueddate')


def sales_summary_by_date() -> QueryBuilder:
    """Resumen de ventas por fecha."""
    return QueryBuilder().select(
        'issueddate',
        'COUNT(*) as total_transactions',
        'SUM(items_quantity) as total_quantity',
        'SUM(total_total) as total_amount'
    ).group_by('issueddate').order_by_desc('issueddate')


def top_customers(limit: int = 10) -> QueryBuilder:
    """Top clientes por ventas."""
    return QueryBuilder().select(
        'customer_customerid',
        'customer_name',
        'COUNT(*) as total_transactions',
        'SUM(total_total) as total_amount'
    ).group_by('customer_customerid', 'customer_name').order_by_desc('SUM(total_total)').limit(limit)


def top_products(limit: int = 10) -> QueryBuilder:
    """Top productos por ventas."""
    return QueryBuilder().select(
        'items_product_sku',
        'items_product_description',
        'SUM(items_quantity) as total_quantity',
        'SUM(total_total) as total_amount'
    ).group_by('items_product_sku', 'items_product_description').order_by_desc('SUM(total_total)').limit(limit) 