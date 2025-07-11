"""
Database connection management for product engine.

This module provides shared database connection functionality
used by both db_manager and db_client modules.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from typing import Optional, Dict, Any, List
import structlog
from contextlib import contextmanager

from .config import config

logger = structlog.get_logger(__name__)


class DatabaseConnection:
    """
    Manages PostgreSQL database connections with connection pooling.
    
    This class provides a shared connection pool and utilities for
    database operations used throughout the product engine.
    """
    
    def __init__(self):
        """Initialize database connection manager."""
        self.logger = logger.bind(component="database_connection")
        self.pool: Optional[ThreadedConnectionPool] = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool."""
        try:
            db_config = config.get_database_config()
            
            # Create connection pool
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=db_config['host'],
                port=int(db_config['port']),
                database=db_config.get('name', db_config.get('database', 'productdb')),
                user=db_config['user'],
                password=db_config['password'],
                cursor_factory=RealDictCursor
            )
            
            self.logger.info(
                "Database connection pool created",
                host=db_config['host'],
                database=db_config.get('name', db_config.get('database', 'productdb'))
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to create database connection pool",
                error=str(e),
                exc_info=True
            )
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for getting a database connection from the pool.
        
        Usage:
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM products")
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(
                "Database operation failed",
                error=str(e),
                exc_info=True
            )
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, commit: bool = True):
        """
        Context manager for getting a database cursor.
        
        Args:
            commit: Whether to commit the transaction at the end.
            
        Usage:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM products")
                results = cursor.fetchall()
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    yield cursor
                    if commit:
                        conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise
    
    def execute_query(self, query: str, params: Optional[tuple] = None, 
                     fetch_one: bool = False, fetch_all: bool = True) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query string.
            params: Query parameters.
            fetch_one: If True, return only the first result.
            fetch_all: If True, return all results.
            
        Returns:
            Query results as list of dictionaries, single dictionary, or None.
        """
        try:
            with self.get_cursor(commit=False) as cursor:
                cursor.execute(query, params)
                
                if fetch_one:
                    result = cursor.fetchone()
                    return dict(result) if result else None
                elif fetch_all:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:
                    return None
        except Exception as e:
            self.logger.error(
                "Query execution failed",
                query=query[:100] + "..." if len(query) > 100 else query,
                error=str(e),
                exc_info=True
            )
            raise
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query.
        
        Args:
            query: SQL query string.
            params: Query parameters.
            
        Returns:
            Number of rows affected.
        """
        try:
            with self.get_cursor(commit=True) as cursor:
                cursor.execute(query, params)
                return cursor.rowcount
        except Exception as e:
            self.logger.error(
                "Update execution failed",
                query=query[:100] + "..." if len(query) > 100 else query,
                error=str(e),
                exc_info=True
            )
            raise
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute a query with multiple parameter sets (batch operation).
        
        Args:
            query: SQL query string.
            params_list: List of parameter tuples.
            
        Returns:
            Total number of rows affected.
        """
        try:
            with self.get_cursor(commit=True) as cursor:
                psycopg2.extras.execute_batch(cursor, query, params_list)
                return cursor.rowcount
        except Exception as e:
            self.logger.error(
                "Batch execution failed",
                query=query[:100] + "..." if len(query) > 100 else query,
                batch_size=len(params_list),
                error=str(e),
                exc_info=True
            )
            raise
    
    def test_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            with self.get_cursor(commit=False) as cursor:
                cursor.execute("SELECT version()")
                result = cursor.fetchone()
                
                if result:
                    self.logger.info(
                        "Database connection test successful",
                        version=result['version']
                    )
                    return True
                else:
                    self.logger.error("Database connection test failed - no result")
                    return False
                    
        except Exception as e:
            self.logger.error(
                "Database connection test failed",
                error=str(e)
            )
            return False
    
    def close(self):
        """Close the connection pool."""
        if self.pool:
            self.pool.closeall()
            self.logger.info("Database connection pool closed")

# Singleton instance
database = DatabaseConnection() 