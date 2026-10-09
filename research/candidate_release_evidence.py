"""Economic robustness screen, separate from frozen historical qualification.

No deployment or future profitability authorization follows from this output.
"""
import math


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def evaluate(evidence):
    full = evidence.get("full", {})
    delay = evidence.get("delay500", {})
    small = evidence.get("capital70", {})
    delay_pf = delay.get("net_profit_factor")
    checks = {
        "frozen_historical_screen": evidence.get("qualified") is True,
        "extra_020_cost_net_positive": positive(full.get("extra_cost_stress", {}).get("0.2")),
        "delay500_net_positive": positive(delay.get("net")),
        "delay500_pf_at_least_110": positive(delay_pf) and delay_pf >= 1.1,
        "capital70_net_positive": positive(small.get("net")),
        "capital70_no_stopout": small.get("native_stopout") is False,
    }
    return dict(checks=checks, historically_robust=all(checks.values()),
                scope="Locked candidate only. Rejected descriptive maximum excluded.",
                independent_review_required=True, genuinely_unseen_oos=False,
                prospective_confirmation="NOT_ESTABLISHED", promotion=False,
                reasons=[key for key, passed in checks.items() if not passed])
