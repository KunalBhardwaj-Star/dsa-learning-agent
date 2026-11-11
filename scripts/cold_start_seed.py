import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np

from bandit.policies.thompson_sampling_policy import ThompsonSamplingPolicy
from data.simulator import TOPICS, DIFFICULTIES, N_TOPICS, N_ARMS, CONTEXT_DIM, topic_difficulty_to_arm

from scripts.leetcode_import.topic_mapper import TAG_TO_TOPIC

MAX_PSEUDO_ATTEMPTS_PER_TOPIC = 15  


def load_profile(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def compute_topic_exposure(data: dict) -> dict:
    exposure = {topic: 0 for topic in TOPICS}
    tag_counts = data["data"]["matchedUser"]["tagProblemCounts"]
    for bucket in ("fundamental", "intermediate", "advanced"):
        for entry in tag_counts[bucket]:
            topic = TAG_TO_TOPIC.get(entry["tagSlug"])
            if topic:
                exposure[topic] += entry["problemsSolved"]
    return exposure


def compute_global_accuracy(data: dict) -> float:
    subs = data["data"]["recentSubmissionList"]
    if not subs:
        return 0.5
    correct = sum(1 for s in subs if s["statusDisplay"] == "Accepted")
    return correct / len(subs)


def compute_difficulty_weights(data: dict) -> dict:
    """Global Easy/Medium/Hard split, used to distribute pseudo-attempts across difficulties."""
    counts = {e["difficulty"]: e["count"] for e in data["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]}
    total = counts["Easy"] + counts["Medium"] + counts["Hard"]
    return {d: counts[d] / total for d in ("Easy", "Medium", "Hard")}


class RealLearnerState:
    """Same tracking shape as data.simulator.SyntheticLearner, but seeded from real
    profile data instead of a hidden random skill — this is what get_context() reads from."""

    def __init__(self):
        self.attempt_counts = np.zeros(N_TOPICS)
        self.correct_counts = np.zeros(N_TOPICS)
        self.last_seen_round = np.full(N_TOPICS, -1)
        self.round = 0

    def get_context(self) -> np.ndarray:
        rolling_accuracy = np.divide(
            self.correct_counts, self.attempt_counts,
            out=np.full(N_TOPICS, 0.5), where=self.attempt_counts > 0
        )
        attempts_norm = np.clip(
            np.log1p(self.attempt_counts) /
            np.log1p(50),
            0,
            1
        )
        recency = np.where(
            self.last_seen_round < 0, 0.0,
            np.exp(-(self.round - self.last_seen_round) / 10.0)
        )
        return np.concatenate([rolling_accuracy, attempts_norm, recency, [1.0]])

    def record(self, topic_idx: int, correct: bool):
        self.attempt_counts[topic_idx] += 1
        if correct:
            self.correct_counts[topic_idx] += 1
        self.last_seen_round[topic_idx] = self.round
        self.round += 1


def seed_bandit_from_profile(
    bandit: ThompsonSamplingPolicy, exposure: dict,
                              global_accuracy: float, difficulty_weights: dict,
                              seed: int = 0) -> RealLearnerState:
    """Feeds pseudo-observations into the bandit, proportional to real exposure per topic."""
    rng = np.random.default_rng(seed)
    state = RealLearnerState()

    max_exposure = max(exposure.values()) if max(exposure.values()) > 0 else 1
    for topic_idx, topic in enumerate(TOPICS):
        n_pseudo = round((exposure[topic] / max_exposure) * MAX_PSEUDO_ATTEMPTS_PER_TOPIC)
        for _ in range(n_pseudo):
            difficulty = rng.choice(DIFFICULTIES, p=[difficulty_weights[d] for d in DIFFICULTIES])
            difficulty_idx = DIFFICULTIES.index(difficulty)
            arm = topic_difficulty_to_arm(topic_idx, difficulty_idx)

            context = state.get_context()  # context BEFORE this pseudo-attempt, same as live use
            correct = rng.random() < global_accuracy
            reward = 1.0 if correct else 0.0  # no weak-topic bonus here — this is a prior, not a live reward

            bandit.update(arm, context, reward)
            state.record(topic_idx, correct)

    return state

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main(profile_path: str | None = None):
    if profile_path is None:
        profile_path = os.path.join(BASE_DIR, "leetcode_data.json")
    data = load_profile(profile_path)
    exposure = compute_topic_exposure(data)
    global_accuracy = compute_global_accuracy(data)
    difficulty_weights = compute_difficulty_weights(data)

    print("Real profile summary:")
    print(f"  Global recent accuracy (proxy applied to all topics): {global_accuracy:.2f}")
    print(f"  Difficulty split: {[(d, round(w,2)) for d, w in difficulty_weights.items()]}")
    print(f"  Topic exposure (solved-count proxy): {exposure}\n")

    bandit = ThompsonSamplingPolicy(
        n_arms=N_ARMS,
        context_dimension=CONTEXT_DIM,
        seed=7,
    )    
    state = seed_bandit_from_profile(bandit, exposure, global_accuracy, difficulty_weights, seed=7)

    print("Pseudo-attempts seeded per topic (capped, exposure-proportional):")
    for i, topic in enumerate(TOPICS):
        print(f"  {topic}: {int(state.attempt_counts[i])} pseudo-attempts, "
              f"{state.correct_counts[i]/state.attempt_counts[i]:.2f} pseudo-accuracy"
              if state.attempt_counts[i] > 0 else f"  {topic}: 0 pseudo-attempts (unexplored)")

    context = state.get_context()

    ranked = sorted(range(N_ARMS), key=lambda a: bandit.expected_reward(a, context), reverse=True)
    print("\nTop 5 arms by posterior-mean expected reward (best guess, no exploration):")
    for arm in ranked[:5]:
        t, d = divmod(arm, len(DIFFICULTIES))
        print(f"  {TOPICS[t]} / {DIFFICULTIES[d]}  (expected reward: {bandit.expected_reward(arm, context):.3f})")

    picked_arm = bandit.select_arm(context)
    t, d = divmod(picked_arm, len(DIFFICULTIES))
    print(f"\nActual first live recommendation (select_arm, includes exploration): "
          f"{TOPICS[t]} / {DIFFICULTIES[d]}")


if __name__ == "__main__":
    main()