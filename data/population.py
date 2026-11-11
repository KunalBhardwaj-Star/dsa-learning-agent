import numpy as np

from data.constants import (
    TOPICS,
    N_TOPICS,
)

def make_skill_population(n_learners: int, seed: int = 0) -> list[np.ndarray]:
    """
    Generates hidden skill profiles (NOT learner objects yet) with diverse
    weak-topic archetypes, so the bandit is validated against more than one
    lucky/unlucky ground truth. Returning skills (not learners) lets the same
    underlying learner be instantiated fresh under each policy being compared,
    for a fair head-to-head.
    Archetypes: broadly-strong, broadly-weak, and single-topic-weak (one per topic).
    """
    rng = np.random.default_rng(seed)
    archetypes = ["strong", "weak"] + TOPICS  # one archetype per topic, plus 2 general ones
    skills = []

    for i in range(n_learners):
        archetype = archetypes[i % len(archetypes)]
        base_skill = rng.uniform(0.55, 0.8, size=N_TOPICS)  # generally competent by default

        if archetype == "strong":
            skill = rng.uniform(0.7, 0.95, size=N_TOPICS)
        elif archetype == "weak":
            skill = rng.uniform(0.15, 0.4, size=N_TOPICS)
        else:
            skill = base_skill.copy()
            weak_topic_idx = TOPICS.index(archetype)
            skill[weak_topic_idx] = rng.uniform(0.1, 0.3)  # secretly weak in exactly one topic

        skills.append(np.clip(skill, 0.02, 0.98))
    return skills