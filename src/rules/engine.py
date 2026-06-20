"""Rule engine - evaluates all rules and picks winner by precedence."""
from src.rules.rules import (
    MissingDataRule,
    IncompleteRequestRule,
    OrderStatusRule,
    RefundAmountVsOrderRule,
    CustomerStatusRule,
    HighValueOrOldOrderRule,
    StandardRefundRule,
)
from src.core.models import Action, Decision, RuleResult


class RuleEngine:
    """Evaluates all rules and picks the most decisive action.

    Ordering note: REJECT rules are listed first for readability (they trigger
    early exit), but the final action is determined by severity, not position.
    Reordering rules is safe — it does not change the outcome. The output
    depends only on what rules fire and their severity levels (REJECT > ESCALATE > APPROVE).
    """

    def __init__(self):
        self.rules = [
            MissingDataRule(),
            OrderStatusRule(),
            IncompleteRequestRule(),
            RefundAmountVsOrderRule(),
            CustomerStatusRule(),
            HighValueOrOldOrderRule(),
            StandardRefundRule(),
        ]

    def run(self, context: dict) -> Decision:
        """Evaluate all rules. Pick the most severe action by precedence.

        Short-circuit only on REJECT (highest severity, nothing can beat it).
        Otherwise, accumulate all results and use max() to pick the winner.

        Args:
            context: dict with customer, order, extracted_amount, etc.

        Returns:
            Decision with action, primary_reason, and full audit trace.
        """
        trace = []

        for rule in self.rules:
            result = rule.evaluate(context)
            if result is not None:
                trace.append(result)

                # REJECT is most decisive — nothing outranks it, so exit early
                if result.action is Action.REJECT:
                    return Decision(
                        action=Action.REJECT,
                        primary_reason=result.reason,
                        trace=trace,
                    )

        # No REJECT fired. Pick the most severe action from what did fire.
        if trace:
            winner = max(trace, key=lambda r: r.action)
        else:
            winner = RuleResult(
                rule="default",
                action=Action.ESCALATE,
                reason="No rule matched (should not happen)",
            )
            trace = [winner]

        return Decision(
            action=winner.action,
            primary_reason=winner.reason,
            trace=trace,
        )
