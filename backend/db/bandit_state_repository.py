import json
from backend.db.connections import get_db_connection
from bandit.policies.thompson_sampling_policy import ThompsonSamplingPolicy


def save_bandit_state(learner_id: int, bandit: ThompsonSamplingPolicy, conn=None) -> None:
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()

    state_json = json.dumps(bandit.to_dict())
    cursor.execute(
        """
        INSERT INTO bandit_state (learner_id, model_params_json)
        VALUES (%s, %s)
        ON CONFLICT (learner_id) DO UPDATE
            SET model_params_json = EXCLUDED.model_params_json
        """,
        (learner_id, state_json),
    )
    conn.commit()

    if own_conn:
        cursor.close()
        conn.close()


def load_bandit_state(learner_id: int, conn=None):
    """Returns a reconstructed policy with the learner's saved beliefs, or None if
    they have no saved state yet -- OR if the saved state doesn't match the current
    to_dict()/from_dict() format (e.g. after a refactor that renamed serialized keys).
    A format mismatch is treated the same as "no state": fall back to a fresh policy
    rather than crashing the whole request."""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT model_params_json FROM bandit_state WHERE learner_id = %s",
        (learner_id,),
    )
    row = cursor.fetchone()

    if own_conn:
        cursor.close()
        conn.close()

    if row is None:
        return None

    try:
        raw_params = row["model_params_json"]
        state = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
        return ThompsonSamplingPolicy.from_dict(state)

    except (KeyError, TypeError, ValueError) as e:
        print(
            f"WARNING: bandit_state for learner_id={learner_id} doesn't match the "
            f"current ThompsonSamplingPolicy format ({e}). Falling back to a fresh "
            f"policy -- this learner's previously saved beliefs are being discarded."
        )
        return None