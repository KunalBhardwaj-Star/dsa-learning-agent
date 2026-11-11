from backend.db.connections import get_db_connection

def create_learner(username: str, conn=None) -> int:
    """Creates a learner if the username doesn't exist yet, otherwise returns their
    existing id -- idempotent, so calling this on every /learners request is safe."""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO learners (username)
        VALUES (%s)
        ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
        RETURNING id
        """,
        (username,),
    )
    learner_id = cursor.fetchone()[0]
    conn.commit()

    if own_conn:
        cursor.close()
        conn.close()
    return learner_id



def get_attempt_history(learner_id: int, conn=None) -> list[dict]:
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT a.id, a.problem_id, p.title, p.difficulty, a.correct,
               a.hints_used, a.time_taken, a.timestamp
        FROM attempts a
        JOIN problems p ON a.problem_id = p.id
        WHERE a.learner_id = %s
        ORDER BY a.timestamp DESC
        """,
        (learner_id,),
    )
    rows = cursor.fetchall()

    if own_conn:
        cursor.close()
        conn.close()
    return rows


def get_learner_by_id(learner_id: int, conn=None) -> dict | None:
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT id, username, created_at FROM learners WHERE id = %s",
        (learner_id,),
    )
    row = cursor.fetchone()

    if own_conn:
        cursor.close()
        conn.close()
    return row


def delete_learner(learner_id: int, conn=None) -> bool:
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM learners WHERE id = %s", (learner_id,))
    deleted = cursor.rowcount > 0
    conn.commit()

    if own_conn:
        cursor.close()
        conn.close()
    return deleted