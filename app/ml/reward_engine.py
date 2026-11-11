from typing import Dict, Any

def compute_composite_reward(
    success: bool,
    time_spent_seconds: int,
    expected_time_minutes: int = 30,
    submission_count: int = 1,
    hints_used: int = 0,
    is_repeat: bool = False,
    w1: float = 1.0,
    w2: float = 1.0,
    w3: float = 1.0,
    w4: float = 1.0,
    w5: float = 1.0,
) -> Dict[str, float]:
    """
    Computes Composite Learning Gain Reward per SRS Section 3.3:
      R_{total} = w1*R_status + w2*R_speed + w3*R_first_try - w4*P_hints - w5*P_repeat

    Components:
      - R_status = +1.0 if success else -0.5
      - R_speed = max(0, 1 - T_actual / T_expected) * 0.5
      - R_first_try = 1.0 if submission_count == 1 else 0.0
      - P_hints = 0.25 * hints_used
      - P_repeat = 0.5 if is_repeat else 0.0

    Returns dict containing R_total and breakdown.
    R_total bounded in [-2.0, +3.0].
    """
    r_status = 1.0 if success else -0.5

    t_actual = float(max(1, time_spent_seconds))
    t_expected = float(max(1, expected_time_minutes * 60))
    r_speed = max(0.0, 1.0 - (t_actual / t_expected)) * 0.5

    r_first_try = 1.0 if submission_count <= 1 else 0.0
    p_hints = 0.25 * float(hints_used)
    p_repeat = 0.5 if is_repeat else 0.0

    r_total = (w1 * r_status) + (w2 * r_speed) + (w3 * r_first_try) - (w4 * p_hints) - (w5 * p_repeat)

    # Clamp bounds to [-2.0, +3.0] per SRS Section 3.3
    r_total_clamped = max(-2.0, min(3.0, float(r_total)))

    return {
        "r_total": r_total_clamped,
        "raw_r_total": r_total,
        "r_status": r_status,
        "r_speed": r_speed,
        "r_first_try": r_first_try,
        "p_hints": p_hints,
        "p_repeat": p_repeat,
    }
