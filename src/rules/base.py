"""Abstract base rule class"""
from abc import ABC, abstractmethod
from typing import Optional


class Rule(ABC):
    """Abstract base rule"""

    @abstractmethod
    def evaluate(self, context: dict) -> tuple[Optional[str], Optional[str]]:
        """
        Evaluate rule and return (action, reasoning) or (None, None) if rule doesn't apply

        Args:
            context: Dictionary with customer, order, extracted_amount, extracted_order_id

        Returns:
            Tuple of (action, reasoning) or (None, None)
        """
        pass
