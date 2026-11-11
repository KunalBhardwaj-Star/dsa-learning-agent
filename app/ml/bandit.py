import numpy as np
from typing import Dict, List, Tuple, Any, Optional

class LinUCB:
    """
    LinUCB Contextual Bandit Engine per SRS-DSA-2026-V2 Specifications.
    
    Feature Vector Dimension: d = 8
    Exploration Parameter: alpha = 0.25 (default)
    
    Equations:
      theta_a = A_a^(-1) * b_a
      p_{a,t} = theta_a^T * x_{u,t} + alpha * sqrt(x_{u,t}^T * A_a^(-1) * x_{u,t})
      a* = argmax_{a in A} p_{a,t}
      
    Update Rule:
      A_a* <- A_a* + x_{u,t} * x_{u,t}^T
      b_a* <- b_a* + R_{total} * x_{u,t}
    """

    def __init__(self, d: int = 8, alpha: float = 0.25, jitter: float = 1e-6):
        self.d = d
        self.alpha = alpha
        self.jitter = jitter

    def _get_identity(self) -> np.ndarray:
        return np.eye(self.d, dtype=np.float64)

    def _get_zero_vector(self) -> np.ndarray:
        return np.zeros((self.d, 1), dtype=np.float64)

    def select_arm(
        self,
        user_context: np.ndarray,
        candidate_arms: List[int],
        bandit_params: Dict[int, Dict[str, Any]]
    ) -> Tuple[int, float, Dict[str, float]]:
        """
        Selects optimal candidate arm maximizing upper confidence bound (p_{a,t}).

        :param user_context: 8-dimensional feature vector x_{u,t} (shape: (8,) or (8,1))
        :param candidate_arms: List of frontend_question_id integers available as arms
        :param bandit_params: Dict mapping arm_id -> {'matrix_a': list/ndarray, 'vector_b': list/ndarray}
        :return: Tuple of (best_arm_id, best_ucb_score, arm_scores_dict)
        """
        x_u = np.asarray(user_context, dtype=np.float64).reshape((self.d, 1))
        best_arm = candidate_arms[0] if candidate_arms else -1
        best_score = -np.inf
        scores = {}

        for arm_id in candidate_arms:
            param = bandit_params.get(arm_id)
            if param and "matrix_a" in param and "vector_b" in param:
                A_a = np.asarray(param["matrix_a"], dtype=np.float64)
                b_a = np.asarray(param["vector_b"], dtype=np.float64).reshape((self.d, 1))
            else:
                A_a = self._get_identity()
                b_a = self._get_zero_vector()

            # Add jitter to diagonal for numerical stability (prevent matrix singularity)
            A_a_reg = A_a + np.eye(self.d) * self.jitter
            A_inv = np.linalg.inv(A_a_reg)

            # Ridge regression estimate: theta_a = A_a^(-1) * b_a
            theta_a = A_inv @ b_a

            # Variance estimate: x_u^T * A_a^(-1) * x_u
            var_term = float((x_u.T @ A_inv @ x_u).item())
            var_term = max(0.0, var_term)

            # Upper Confidence Bound calculation
            expected_reward = float((theta_a.T @ x_u).item())
            exploration_bonus = self.alpha * np.sqrt(var_term)
            p_a = expected_reward + exploration_bonus

            scores[arm_id] = float(p_a)
            if p_a > best_score:
                best_score = float(p_a)
                best_arm = arm_id

        return best_arm, float(best_score), scores

    def update_arm(
        self,
        arm_id: int,
        user_context: np.ndarray,
        reward: float,
        current_A: Optional[np.ndarray] = None,
        current_b: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Updates LinUCB parameters for selected arm.

        :param arm_id: Question ID / Arm ID
        :param user_context: 8-dimensional feature vector x_{u,t}
        :param reward: Scalar composite feedback reward R_{total}
        :param current_A: Existing (8,8) matrix A_a or None (defaults to Identity)
        :param current_b: Existing (8,1) vector b_a or None (defaults to Zeros)
        :return: Updated (A_a, b_a) as double precision numpy arrays
        """
        x_u = np.asarray(user_context, dtype=np.float64).reshape((self.d, 1))

        if current_A is None:
            A_a = self._get_identity()
        else:
            A_a = np.asarray(current_A, dtype=np.float64)

        if current_b is None:
            b_a = self._get_zero_vector()
        else:
            b_a = np.asarray(current_b, dtype=np.float64).reshape((self.d, 1))

        # Parameter Update Rule per SRS:
        # A_a* <- A_a* + x_u * x_u^T
        # b_a* <- b_a* + R_{total} * x_u
        updated_A = A_a + (x_u @ x_u.T)
        updated_b = b_a + (reward * x_u)

        return updated_A, updated_b
