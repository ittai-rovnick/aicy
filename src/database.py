"""Database access layer using Repository pattern"""
from abc import ABC, abstractmethod
from typing import Optional
import json
import os

from src.models import Customer, Order
from config.config import DATA_DIR


class DatabaseInterface(ABC):
    """Abstract database interface"""

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


class JsonLocalDatabase(DatabaseInterface):
    """Local JSON file database implementation"""

    def __init__(self):
        self.customers_file = os.path.join(DATA_DIR, "customers.json")
        self.orders_file = os.path.join(DATA_DIR, "orders.json")
        self._load_data()

    def _load_data(self):
        """Load JSON files into memory"""
        with open(self.customers_file, "r") as f:
            self.customers = json.load(f)

        with open(self.orders_file, "r") as f:
            self.orders = json.load(f)

    def get_customer(
        self, customer_id: Optional[str] = None, email: Optional[str] = None
    ) -> Optional[Customer]:
        """Fetch customer by ID or email"""
        if customer_id:
            for customer in self.customers:
                if customer.get("id") == customer_id:
                    return Customer(**customer)

        if email:
            for customer in self.customers:
                if customer.get("email") == email:
                    return Customer(**customer)

        return None

    def get_order(self, order_id: str) -> Optional[Order]:
        """Fetch order by order ID"""
        for order in self.orders:
            if order.get("order_id") == order_id:
                return Order(**order)
        return None

    def get_customer_orders(self, customer_id: str) -> list[Order]:
        """Fetch all orders for a customer"""
        customer_orders = []
        for order in self.orders:
            if order.get("customer_id") == customer_id:
                customer_orders.append(Order(**order))
        return customer_orders
