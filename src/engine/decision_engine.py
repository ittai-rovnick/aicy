"""Decision engine - thin wrapper around RuleEngine."""
from src.core.models import Decision
from src.rules.engine import RuleEngine


def decide(context: dict) -> Decision:
    """Evaluate context through all rules; return Decision with action and trace."""
    return RuleEngine().run(context)
