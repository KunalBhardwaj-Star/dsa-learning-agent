from backend.db.connections import get_db_connection

from fetcher import fetch_all_problems
from transformer import transform_problems
from problem_repository import (
    insert_problems,
    insert_problem_topics,
)


def main():
    print("Fetching problems from LeetCode...")

    problems = fetch_all_problems()

    print(f"Fetched {len(problems)} problems.")

    (
        problem_rows,
        topic_rows,
        skipped_paid,
        skipped_unmapped,
    ) = transform_problems(problems)

    print(f"Skipped paid problems: {skipped_paid}")
    print(f"Skipped unmapped problems: {skipped_unmapped}")
    print(f"Problems to insert/update: {len(problem_rows)}")
    print(f"Topic mappings: {len(topic_rows)}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        insert_problems(cursor, problem_rows)
        print(
            f"Problems affected (inserted/updated): "
            f"{cursor.rowcount}"
        )

        insert_problem_topics(cursor, topic_rows)
        print(
            f"New topic mappings inserted: "
            f"{cursor.rowcount}"
        )

        conn.commit()

    finally:
        cursor.close()
        conn.close()

    print("\nDatabase seed completed successfully.")
    print(
        "Note: expected_complexity remains NULL "
        "until manually tagged."
    )


if __name__ == "__main__":
    main()