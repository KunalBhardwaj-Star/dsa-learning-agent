import numpy as np

from .policy import Policy


class RandomPolicy(Policy):
    """
    Random recommendation policy.

    Used as a baseline for evaluating learning policies.
    """

    def __init__(
        self,
        num_arms: int,
        seed: int | None = None,
    ):
        self.num_arms = num_arms
        self.rng = np.random.default_rng(seed)

    def select_arm(self, context_vector: np.ndarray) -> int:
        return int(self.rng.integers(0, self.num_arms))

    def update(
        self,
        arm: int,
        context_vector: np.ndarray,
        reward: float,
    ) -> None:
        """
        Random policy does not learn from feedback.
        """
        return None

    