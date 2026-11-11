def insert_problems(cursor, problem_rows):
    cursor.executemany(
        """
        INSERT INTO problems
        (
            id,
            title,
            difficulty,
            leetcode_slug
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            difficulty = EXCLUDED.difficulty,
            leetcode_slug = EXCLUDED.leetcode_slug
        """,
        problem_rows,
    )


def insert_problem_topics(cursor, topic_rows):
    cursor.executemany(
        """
        INSERT INTO problem_topics
        (
            problem_id,
            topic
        )
        VALUES
        (
            %s,
            %s
        )
        ON CONFLICT (problem_id, topic) DO NOTHING
        """,
        topic_rows,
    )