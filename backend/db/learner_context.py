import numpy as np

from backend.db.connections import get_db_connection

from data.constants import (
    TOPICS,
    N_TOPICS,
)

def get_learner_context(learner_id: int, conn=None) -> np.ndarray:
    """
    Builds the same-shaped context vector as SyntheticLearner.get_context():
    [rolling_accuracy(18), attempts_norm(18), recency(18), bias(1)] = 55-dim.

    A single attempt on a multi-topic problem (e.g. tagged Arrays + Greedy)
    counts as evidence toward BOTH topics -- this is the design decision we
    made explicitly: joining through problem_topics means one real attempt
    can update multiple topics' rolling accuracy, matching the fact that
    solving a multi-tagged problem really is evidence about all its topics.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT pt.topic,
               COUNT(*) AS attempt_count,
               SUM(CASE WHEN a.correct THEN 1 ELSE 0 END) AS correct_count,
               MAX(a.timestamp) AS last_attempt_time
        FROM attempts a
        JOIN problem_topics pt ON a.problem_id = pt.problem_id
        WHERE a.learner_id = %s
        GROUP BY pt.topic

        """,
        (learner_id,),
    )
    rows = {r["topic"]: r for r in cursor.fetchall()}

    cursor.execute(
        "SELECT MAX(timestamp) AS now_ts FROM attempts WHERE learner_id = %s",
        (learner_id,),
    )
    now_ts = cursor.fetchone()["now_ts"]

    if own_conn:
        cursor.close()
        conn.close()

    rolling_accuracy = np.full(N_TOPICS, 0.5)
    attempts_norm = np.zeros(N_TOPICS)
    recency = np.zeros(N_TOPICS)

    for i, topic in enumerate(TOPICS):
        row = rows.get(topic)
        if row is None or row["attempt_count"] == 0:
            continue
        attempt_count = row["attempt_count"]
        correct_count = row["correct_count"] or 0

        rolling_accuracy[i] = correct_count / attempt_count
        # log-scaled exposure: diminishing returns per additional attempt,
        # near-1.0 around 50 attempts instead of a hard linear cap at 20
        attempts_norm[i] = min(np.log1p(attempt_count) / np.log1p(50), 1.0)

        if now_ts is not None and row["last_attempt_time"] is not None:
            days_since = (now_ts - row["last_attempt_time"]).total_seconds() / 86400.0
            recency[i] = np.exp(-days_since / 10.0)

    return np.concatenate([rolling_accuracy, attempts_norm, recency, [1.0]])


def get_learner_analytics(learner_id: int, conn=None) -> dict:
    """Returns structured analytics breakdown per topic for visualization & insights."""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT pt.topic,
               COUNT(*) AS attempt_count,
               SUM(CASE WHEN a.correct THEN 1 ELSE 0 END) AS correct_count,
               MAX(a.timestamp) AS last_attempt_time
        FROM attempts a
        JOIN problem_topics pt ON a.problem_id = pt.problem_id
        WHERE a.learner_id = %s
        GROUP BY pt.topic
        """,
        (learner_id,),
    )
    rows = {r["topic"]: r for r in cursor.fetchall()}

    cursor.execute(
        "SELECT COUNT(*) AS total_attempts, SUM(CASE WHEN correct THEN 1 ELSE 0 END) AS total_correct FROM attempts WHERE learner_id = %s",
        (learner_id,),
    )
    overall_row = cursor.fetchone()

    if own_conn:
        cursor.close()
        conn.close()

    total_attempts = overall_row["total_attempts"] if overall_row else 0
    total_correct = overall_row["total_correct"] if (overall_row and overall_row["total_correct"]) else 0
    overall_accuracy = (total_correct / total_attempts) if total_attempts > 0 else 0.0

    topic_stats = []
    for topic in TOPICS:
        row = rows.get(topic)
        attempts = row["attempt_count"] if row else 0
        correct = (row["correct_count"] or 0) if row else 0
        acc = (correct / attempts) if attempts > 0 else 0.5
        topic_stats.append({
            "topic": topic,
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(acc, 3),
        })

    # Sort topics by accuracy & attempts for strengths and weaknesses
    attempted_topics = [t for t in topic_stats if t["attempts"] > 0]
    attempted_topics.sort(key=lambda x: x["accuracy"])

    weakest = [t["topic"] for t in attempted_topics[:3]]
    strongest = [t["topic"] for t in reversed(attempted_topics[-3:])] if attempted_topics else []

    return {
        "learner_id": learner_id,
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "overall_accuracy": round(overall_accuracy, 3),
        "topic_breakdown": topic_stats,
        "weakest_topics": weakest,
        "strongest_topics": strongest,
    }

