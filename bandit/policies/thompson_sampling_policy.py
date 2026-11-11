import numpy as np

from bandit.policies.policy import Policy


class ThompsonSamplingPolicy(Policy):
    def __init__(
        self,
        n_arms: int,
        context_dimension: int,
        noise_variance: float = 0.03,
        prior_variance: float = 0.35,
        seed: int | None = None,
    ):
        self.n_arms = n_arms
        self.context_dimension = context_dimension
        self.noise_variance = noise_variance
        self.rng = np.random.default_rng(seed)
        self._jitter = 1e-9

        self._precision_inverse = [
            np.eye(self.context_dimension) / prior_variance
            for _ in range(n_arms)
        ]

        self._posterior_vector = [
            np.zeros(self.context_dimension)
            for _ in range(n_arms)
        ]

        self._cholesky_cache = [
            np.linalg.cholesky(
                self._precision_inverse[arm] * self.noise_variance
                + np.eye(self.context_dimension) * self._jitter
            )
            for arm in range(n_arms)
        ]

    def _mean_weights(self, arm: int) -> np.ndarray:
        return self._precision_inverse[arm] @ self._posterior_vector[arm]

    def select_arm(self, context: np.ndarray) -> int:
        best_arm = 0
        best_score = -np.inf

        for arm in range(self.n_arms):
            mean_weights = self._mean_weights(arm)

            random_vector = self.rng.standard_normal(self.context_dimension)

            sampled_weights = (
                mean_weights
                + self._cholesky_cache[arm] @ random_vector
            )

            predicted_reward = context @ sampled_weights

            if predicted_reward > best_score:
                best_score = predicted_reward
                best_arm = arm

        return best_arm

    def update(
        self,
        arm: int,
        context: np.ndarray,
        reward: float,
    ) -> None:

        precision_inverse = self._precision_inverse[arm]

        projected_context = precision_inverse @ context

        denominator = 1.0 + context @ projected_context

        updated_precision_inverse = (
            precision_inverse
            - np.outer(projected_context, projected_context)
            / denominator
        )

        self._precision_inverse[arm] = updated_precision_inverse

        self._posterior_vector[arm] += reward * context

        self._cholesky_cache[arm] = np.linalg.cholesky(
            updated_precision_inverse * self.noise_variance
            + np.eye(self.context_dimension) * self._jitter
        )

    def expected_reward(
        self,
        arm: int,
        context: np.ndarray,
    ) -> float:
        return float(
            context @ self._mean_weights(arm)
        )

    def to_dict(self) -> dict:
        return {
            "n_arms": self.n_arms,
            "context_dimension": self.context_dimension,
            "noise_variance": self.noise_variance,
            "precision_inverse": [
                matrix.tolist()
                for matrix in self._precision_inverse
            ],
            "posterior_vector": [
                vector.tolist()
                for vector in self._posterior_vector
            ],
        }

    @classmethod
    def from_dict(
        cls,
        state: dict,
        seed: int | None = None,
    ) -> "ThompsonSamplingPolicy":

        policy = cls(
            n_arms=state["n_arms"],
            context_dimension=state["context_dimension"],
            noise_variance=state["noise_variance"],
            seed=seed,
        )

        policy._precision_inverse = [
            np.array(matrix)
            for matrix in state["precision_inverse"]
        ]

        policy._posterior_vector = [
            np.array(vector)
            for vector in state["posterior_vector"]
        ]

        policy._cholesky_cache = [
            np.linalg.cholesky(
                policy._precision_inverse[arm] * policy.noise_variance
                + np.eye(policy.context_dimension) * policy._jitter
            )
            for arm in range(policy.n_arms)
        ]

        return policy