from data.constants import N_DIFFICULTIES


def arm_to_topic_difficulty(arm: int) -> tuple[int, int]:
    return divmod(arm, N_DIFFICULTIES)


def topic_difficulty_to_arm(
    topic_index: int,
    difficulty_index: int,
) -> int:
    return topic_index * N_DIFFICULTIES + difficulty_index