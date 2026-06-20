"""Abstract base rule class"""
from abc import ABC, abstractmethod
from typing import Optional
from src.core.models import RuleResult


class Rule(ABC):
    """Abstract base class for decision rules.

    Each rule evaluates facts and returns a RuleResult if it fires,
    or None if it doesn't apply. The Action in the result determines
    precedence: REJECT overrides all, ESCALATE overrides APPROVE.
    """

    @abstractmethod
    def evaluate(self, context: dict) -> Optional[RuleResult]:
        """
        Evaluate this rule against facts.

        Args:
            context: Dictionary with customer, order, extracted_amount, etc.

        Returns:
            RuleResult if rule fires, None otherwise
        """
        pass
