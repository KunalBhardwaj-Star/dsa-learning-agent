
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib.pyplot as plt

from bandit.policies.thompson_sampling_policy import ThompsonSamplingPolicy
from bandit.policies.random_policy import RandomPolicy
from data.simulator import (
    SyntheticLearner, make_skill_population, N_ARMS, CONTEXT_DIM,
    N_DIFFICULTIES, arm_to_topic_difficulty
)

N_LEARNERS = 20
N_ROUNDS = 500  # increased from 300: 54 arms need more data to converge than 24 did
SEED = 42


def oracle_best_expected_reward(learner: SyntheticLearner) -> float:
    best = -np.inf
    for arm in range(N_ARMS):
        t, d = arm_to_topic_difficulty(arm)
        best = max(best, learner.expected_reward(t, d))
    return best


def run_policy(skill: np.ndarray, policy_name: str, seed: int) -> np.ndarray:
    """Runs one learner for N_ROUNDS under one policy. Returns per-round regret array."""
    rng = np.random.default_rng(seed)
    learner = SyntheticLearner(skill=skill, rng=rng)

    if policy_name == "thompson":
        policy = ThompsonSamplingPolicy(n_arms=N_ARMS, context_dimension=CONTEXT_DIM, seed=seed)
    elif policy_name == "random":
        policy = RandomPolicy(num_arms=N_ARMS, seed=seed)
    else:
        raise ValueError(policy_name)

    regrets = np.zeros(N_ROUNDS)
    for round_i in range(N_ROUNDS):
        context = learner.get_context()
        best_expected = oracle_best_expected_reward(learner)

        arm = policy.select_arm(context)
        t, d = arm_to_topic_difficulty(arm)
        chosen_expected = learner.expected_reward(t, d)  # for regret (uses true model, not realized noise)

        realized_reward = learner.take_action(arm)  # this also advances the learner's state
        policy.update(arm, context, realized_reward)

        regrets[round_i] = best_expected - chosen_expected

    return regrets


def main():
    skills = make_skill_population(N_LEARNERS, seed=SEED)

    thompson_regrets = np.zeros((N_LEARNERS, N_ROUNDS))
    random_regrets = np.zeros((N_LEARNERS, N_ROUNDS))

    for i, skill in enumerate(skills):
        thompson_regrets[i] = run_policy(skill, "thompson", seed=SEED + i)
        random_regrets[i] = run_policy(skill, "random", seed=SEED + i)

    thompson_cumulative = np.cumsum(thompson_regrets.mean(axis=0))
    random_cumulative = np.cumsum(random_regrets.mean(axis=0))

    print(f"Final cumulative regret after {N_ROUNDS} rounds (avg over {N_LEARNERS} learners):")
    print(f"  Thompson Sampling: {thompson_cumulative[-1]:.2f}")
    print(f"  Random baseline:   {random_cumulative[-1]:.2f}")
    print(f"  Regret reduction:  {(1 - thompson_cumulative[-1] / random_cumulative[-1]) * 100:.1f}%")

    plt.figure(figsize=(9, 5.5))
    plt.plot(thompson_cumulative, label="Thompson Sampling", linewidth=2, color="#2563eb")
    plt.plot(random_cumulative, label="Random baseline", linewidth=2, color="#dc2626", linestyle="--")
    plt.xlabel("Round")
    plt.ylabel("Cumulative regret")
    plt.title(f"Cumulative Regret: Thompson Sampling vs Random ({N_LEARNERS} synthetic learners)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regret_curve.png")
    plt.savefig(out_path, dpi=150)
    print(f"\nSaved regret curve to {out_path}")


if __name__ == "__main__":
    main()