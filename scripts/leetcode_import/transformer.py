from topic_mapper import map_all_topics


def transform_problems(problems: list[dict]):
    problem_rows = []
    topic_rows = []

    skipped_paid = 0
    skipped_unmapped = 0

    for problem in problems:

        if problem["paidOnly"]:
            skipped_paid += 1
            continue

        topics = map_all_topics(problem["topicTags"])

        if not topics:
            skipped_unmapped += 1
            continue

        try:
            problem_id = int(problem["frontendQuestionId"])
        except (ValueError, TypeError):
            print(
                f"Skipping invalid problem id: "
                f"{problem.get('frontendQuestionId')}"
            )
            continue

        problem_rows.append(
            (
                problem_id,
                problem["title"],
                problem["difficulty"],
                problem["titleSlug"],
            )
        )

        for topic in topics:
            topic_rows.append((problem_id, topic))

    return (
        problem_rows,
        topic_rows,
        skipped_paid,
        skipped_unmapped,
    )