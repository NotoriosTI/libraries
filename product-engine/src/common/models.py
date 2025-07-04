"""
Data models for product engine.

This module defines the data structures used throughout the product engine
for representing products, search results, and other data objects.
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProductData:
    """
    Data class representing a product from Odoo.
    
    This is used for data transfer between different components
    of the product engine system.
    """
    sku: str
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_active: bool = True
    list_price: float = 0.0
    standard_price: float = 0.0
    product_type: Optional[str] = None
    barcode: Optional[str] = None
    weight: float = 0.0
    volume: float = 0.0
    sale_ok: bool = True
    purchase_ok: bool = True
    uom_id: Optional[int] = None
    uom_name: Optional[str] = None
    company_id: Optional[int] = None
    text_for_embedding: Optional[str] = None
    embedding: Optional[List[float]] = None
    last_update: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'sku': self.sku,
            'name': self.name,
            'description': self.description,
            'category_id': self.category_id,
            'category_name': self.category_name,
            'is_active': self.is_active,
            'list_price': self.list_price,
            'standard_price': self.standard_price,
            'product_type': self.product_type,
            'barcode': self.barcode,
            'weight': self.weight,
            'volume': self.volume,
            'sale_ok': self.sale_ok,
            'purchase_ok': self.purchase_ok,
            'uom_id': self.uom_id,
            'uom_name': self.uom_name,
            'company_id': self.company_id,
            'text_for_embedding': self.text_for_embedding,
            'embedding': self.embedding,
            'last_update': self.last_update,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductData':
        """Create ProductData from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'ProductData':
        """Create ProductData from database row."""
        return cls(
            sku=row['sku'],
            name=row['name'],
            description=row.get('description'),
            category_id=row.get('category_id'),
            category_name=row.get('category_name'),
            is_active=row.get('is_active', True),
            list_price=float(row.get('list_price', 0)),
            standard_price=float(row.get('standard_price', 0)),
            product_type=row.get('product_type'),
            barcode=row.get('barcode'),
            weight=float(row.get('weight', 0)),
            volume=float(row.get('volume', 0)),
            sale_ok=row.get('sale_ok', True),
            purchase_ok=row.get('purchase_ok', True),
            uom_id=row.get('uom_id'),
            uom_name=row.get('uom_name'),
            company_id=row.get('company_id'),
            text_for_embedding=row.get('text_for_embedding'),
            embedding=row.get('embedding'),
            last_update=row.get('last_update'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )


@dataclass
class SearchResult:
    """
    Data class representing a search result.
    
    Contains the product data plus search-specific information
    like relevance scores and search type.
    """
    # Product data
    sku: str
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_active: bool = True
    list_price: float = 0.0
    standard_price: float = 0.0
    product_type: Optional[str] = None
    barcode: Optional[str] = None
    weight: float = 0.0
    volume: float = 0.0
    sale_ok: bool = True
    purchase_ok: bool = True
    uom_id: Optional[int] = None
    uom_name: Optional[str] = None
    company_id: Optional[int] = None
    text_for_embedding: Optional[str] = None
    last_update: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Search-specific fields
    search_type: str = "unknown"  # "exact_sku", "semantic", etc.
    relevance_score: float = 0.0  # Overall relevance (0.0 to 1.0)
    similarity_score: Optional[float] = None  # Cosine similarity for semantic search
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'sku': self.sku,
            'name': self.name,
            'description': self.description,
            'category_id': self.category_id,
            'category_name': self.category_name,
            'is_active': self.is_active,
            'list_price': self.list_price,
            'standard_price': self.standard_price,
            'product_type': self.product_type,
            'barcode': self.barcode,
            'weight': self.weight,
            'volume': self.volume,
            'sale_ok': self.sale_ok,
            'purchase_ok': self.purchase_ok,
            'uom_id': self.uom_id,
            'uom_name': self.uom_name,
            'company_id': self.company_id,
            'text_for_embedding': self.text_for_embedding,
            'last_update': self.last_update,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'search_type': self.search_type,
            'relevance_score': self.relevance_score,
            'similarity_score': self.similarity_score
        }
    
    @classmethod
    def from_product_data(cls, product: ProductData, search_type: str = "unknown", 
                         relevance_score: float = 0.0, similarity_score: Optional[float] = None) -> 'SearchResult':
        """Create SearchResult from ProductData."""
        return cls(
            sku=product.sku,
            name=product.name,
            description=product.description,
            category_id=product.category_id,
            category_name=product.category_name,
            is_active=product.is_active,
            list_price=product.list_price,
            standard_price=product.standard_price,
            product_type=product.product_type,
            barcode=product.barcode,
            weight=product.weight,
            volume=product.volume,
            sale_ok=product.sale_ok,
            purchase_ok=product.purchase_ok,
            uom_id=product.uom_id,
            uom_name=product.uom_name,
            company_id=product.company_id,
            text_for_embedding=product.text_for_embedding,
            last_update=product.last_update,
            created_at=product.created_at,
            updated_at=product.updated_at,
            search_type=search_type,
            relevance_score=relevance_score,
            similarity_score=similarity_score
        )
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any], search_type: str = "unknown",
                   relevance_score: float = 0.0, similarity_score: Optional[float] = None) -> 'SearchResult':
        """Create SearchResult from database row."""
        return cls(
            sku=row['sku'],
            name=row['name'],
            description=row.get('description'),
            category_id=row.get('category_id'),
            category_name=row.get('category_name'),
            is_active=row.get('is_active', True),
            list_price=float(row.get('list_price', 0)),
            standard_price=float(row.get('standard_price', 0)),
            product_type=row.get('product_type'),
            barcode=row.get('barcode'),
            weight=float(row.get('weight', 0)),
            volume=float(row.get('volume', 0)),
            sale_ok=row.get('sale_ok', True),
            purchase_ok=row.get('purchase_ok', True),
            uom_id=row.get('uom_id'),
            uom_name=row.get('uom_name'),
            company_id=row.get('company_id'),
            text_for_embedding=row.get('text_for_embedding'),
            last_update=row.get('last_update'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            search_type=search_type,
            relevance_score=relevance_score,
            similarity_score=similarity_score
        ) 