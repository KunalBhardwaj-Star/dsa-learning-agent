import math
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, Optional

LAMBDA_DECAY = 0.05

def compute_decay_factor(last_practiced_at: Optional[datetime], now: Optional[datetime] = None) -> float:
    """
    Computes Exponential Skill Decay per SRS Section 3.1:
      decay_factor = exp(-lambda * delta_t_days) with lambda = 0.05
    """
    if last_practiced_at is None:
        return 1.0

    if now is None:
        now = datetime.now(timezone.utc)

    if last_practiced_at.tzinfo is None:
        last_practiced_at = last_practiced_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    delta_seconds = max(0.0, (now - last_practiced_at).total_seconds())
    delta_days = delta_seconds / 86400.0
    return float(math.exp(-LAMBDA_DECAY * delta_days))


def construct_context_vector(
    acc_20: float = 0.5,
    s_graph: float = 0.5,
    s_dp: float = 0.5,
    s_tree: float = 0.5,
    s_greedy: float = 0.5,
    contest_rating: float = 1500.0,
    z_speed: float = 0.5,
    decay_factor: float = 1.0,
) -> np.ndarray:
    """
    Constructs the 8-dimensional context vector x_{u,t} per SRS Section 3.1:
      x_{u,t} = [ acc_20, S_graph, S_dp, S_tree, S_greedy, contest_rating, Z_speed, decay_factor ]^T
    """
    # Normalize contest rating (1500 baseline -> 0.5, max 3000 -> 1.0)
    norm_contest_rating = max(0.0, min(1.0, float(contest_rating) / 3000.0))

    vector = np.array(
        [
            float(acc_20),
            float(s_graph),
            float(s_dp),
            float(s_tree),
            float(s_greedy),
            norm_contest_rating,
            float(z_speed),
            float(decay_factor),
        ],
        dtype=np.float64,
    )
    return vector
