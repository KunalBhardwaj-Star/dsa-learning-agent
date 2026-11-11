import numpy as np

#E:\dsa-learning-agent\bandit\policies\thompson_sampling_policy.py

from bandit.policies.thompson_sampling_policy import ThompsonSamplingPolicy

policy = ThompsonSamplingPolicy(
    n_arms=54,
    context_dimension=55,
)

state = policy.to_dict()

print(state.keys())

policy2 = ThompsonSamplingPolicy.from_dict(state)

print("Success!")