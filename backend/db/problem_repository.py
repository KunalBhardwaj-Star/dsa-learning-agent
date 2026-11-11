
from backend.db.connections import get_db_connection

def get_problem(topic: str, difficulty: str, learner_id: int, conn=None) -> dict | None:
    """
    Picks one real problem matching (topic, difficulty), preferring one the
    learner hasn't attempted before. Falls back to their least-recently-attempted
    match if every problem in this (topic, difficulty) bucket has already been tried.
    Returns None only if no problem exists at all for this (topic, difficulty) --
    a real data gap, not something calling code should silently ignore.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # unattempted first
    cursor.execute(
        """
        SELECT p.id, p.title, p.leetcode_slug, p.difficulty, p.expected_complexity
        FROM problems p
        JOIN problem_topics pt ON p.id = pt.problem_id
        WHERE pt.topic = %s AND p.difficulty = %s
          AND p.id NOT IN (
              SELECT problem_id FROM attempts WHERE learner_id = %s
          )
        LIMIT 1
        """,
        (topic, difficulty, learner_id),
    )
    row = cursor.fetchone()

    if row is None:
        # every matching problem already attempted -- fall back to least-recently-attempted
        cursor.execute(
            """
            SELECT p.id, p.title, p.leetcode_slug, p.difficulty, p.expected_complexity
            FROM problems p
            JOIN problem_topics pt ON p.id = pt.problem_id
            JOIN attempts a ON a.problem_id = p.id AND a.learner_id = %s
            WHERE pt.topic = %s AND p.difficulty = %s
            GROUP BY p.id, p.title, p.leetcode_slug, p.difficulty, p.expected_complexity
            ORDER BY MAX(a.timestamp) ASC
            LIMIT 1
            """,
            (learner_id, topic, difficulty),
        )
        row = cursor.fetchone()

    if own_conn:
        cursor.close()
        conn.close()

    return row  # None means this (topic, difficulty) bucket has zero problems -- a real gap to fill


def get_problem_by_id(problem_id: int, conn=None) -> dict | None:
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT p.id, p.title, p.leetcode_slug, p.difficulty, p.expected_complexity
        FROM problems p
        WHERE p.id = %s
        """,
        (problem_id,),
    )
    row = cursor.fetchone()

    if row:
        cursor.execute(
            "SELECT topic FROM problem_topics WHERE problem_id = %s",
            (problem_id,),
        )
        row["topics"] = [t["topic"] for t in cursor.fetchall()]

    if own_conn:
        cursor.close()
        conn.close()

    return row


def list_problems(topic: str | None = None, difficulty: str | None = None, limit: int = 50, conn=None) -> list[dict]:
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT DISTINCT p.id, p.title, p.leetcode_slug, p.difficulty, p.expected_complexity
        FROM problems p
        LEFT JOIN problem_topics pt ON p.id = pt.problem_id
        WHERE 1=1
    """
    params = []

    if topic:
        query += " AND pt.topic = %s"
        params.append(topic)
    if difficulty:
        query += " AND p.difficulty = %s"
        params.append(difficulty)

    query += " ORDER BY p.id ASC LIMIT %s"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    if own_conn:
        cursor.close()
        conn.close()

    return rows


