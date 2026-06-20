"""Abstract database interface"""
from abc import ABC, abstractmethod
from typing import Optional

from src.models import Customer, Order


class DatabaseInterface(ABC):
    """Abstract database interface - Repository Pattern"""

    @abstractmethod
    def get_customer(
        self, customer_id: Optional[str] = None, email: Optional[str] = None
    ) -> Optional[Customer]:
        """Fetch customer by ID or email"""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """Fetch order by order ID"""
        pass

    @abstractmethod
    def get_customer_orders(self, customer_id: str) -> list[Order]:
        """Fetch all orders for a customer"""
        pass
