import numpy as np

from data.constants import (
    TOPICS,
    DIFFICULTIES,
    DIFFICULTY_LEVEL,
    N_TOPICS,
)

from data.mappings import arm_to_topic_difficulty

class SyntheticLearner:
    def __init__(self, skill: np.ndarray, rng: np.random.Generator):
        """skill: hidden array of length N_TOPICS, each in [0, 1]. Never exposed to the bandit."""
        self.skill = skill
        self.rng = rng
        self.attempt_counts = np.zeros(N_TOPICS)
        self.correct_counts = np.zeros(N_TOPICS)
        self.last_seen_round = np.full(N_TOPICS, -1)
        self.round = 0

    # ---- context the bandit is allowed to see ----
    def get_context(self) -> np.ndarray:
        rolling_accuracy = np.divide(
            self.correct_counts, self.attempt_counts,
            out=np.full(N_TOPICS, 0.5), where=self.attempt_counts > 0
        )
        # log-scaled exposure, matching db.py exactly -- diminishing returns per
        # attempt, near-1.0 around 50 attempts. MUST stay identical to db.py's
        # get_learner_context(), since this is what the bandit's hyperparameters
        # are validated against; any mismatch here is a train/serve skew.
        attempts_norm = np.clip(np.log1p(self.attempt_counts) / np.log1p(50), 0, 1)
        recency = np.where(
            self.last_seen_round < 0, 0.0,
            np.exp(-(self.round - self.last_seen_round) / 10.0)
        )
        return np.concatenate([rolling_accuracy, attempts_norm, recency, [1.0]])  # bias term

    def topic_is_weak(self, topic_idx: int) -> bool:
        if self.attempt_counts[topic_idx] == 0:
            return False  # unseen isn't "weak" yet — don't reward for it
        return (self.correct_counts[topic_idx] / self.attempt_counts[topic_idx]) < 0.5

    # ---- hidden mechanics, used both to simulate outcomes and to compute the oracle ----
    def _prob_correct(self, topic_idx: int, difficulty_idx: int) -> float:
        gap = self.skill[topic_idx] - DIFFICULTY_LEVEL[DIFFICULTIES[difficulty_idx]]
        return 1.0 / (1.0 + np.exp(-6.0 * gap))  # logistic: sharper skill-vs-difficulty transition

    def expected_reward(self, topic_idx: int, difficulty_idx: int) -> float:
        """True expected reward for this action, using hidden skill. Used ONLY for the oracle/regret calc."""
        p = self._prob_correct(topic_idx, difficulty_idx)
        weak_bonus = 0.3 if self.topic_is_weak(topic_idx) else 0.0
        return p * (1.0 + weak_bonus)

    def take_action(self, arm: int) -> float:
        """Simulate the actual outcome of recommending `arm`. Returns the realized reward."""
        topic_idx, difficulty_idx = arm_to_topic_difficulty(arm)
        p = self._prob_correct(topic_idx, difficulty_idx)
        correct = self.rng.random() < p
        weak_bonus = 0.3 if (correct and self.topic_is_weak(topic_idx)) else 0.0
        reward = (1.0 if correct else 0.0) + weak_bonus

        self.attempt_counts[topic_idx] += 1
        if correct:
            self.correct_counts[topic_idx] += 1
        self.last_seen_round[topic_idx] = self.round
        self.round += 1
        return reward