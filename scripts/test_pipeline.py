import os
import sys

# Add project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.database import SessionLocal
from backend.db.models import User
from backend.services.recommendation_service import recommend_next_problem
from backend.services.attempt_service import record_problem_attempt
from backend.services.mock_interview_service import create_mock_interview

def run_test():
    session = SessionLocal()
    try:
        user = session.query(User).first()
        if not user:
            print("No user found in PostgreSQL. Register a user first via auth_service or API.")
            return

        print(f"=== 1. LinUCB Recommendation Test for User: {user.username} ===")
        rec = recommend_next_problem(user_id=user.id, session=session)
        print(f"Recommended Question: #{rec['problem_id']} - {rec['title']} ({rec['difficulty']})")
        print(f"UCB Score: {rec['ucb_score']} | Candidate Pool Size: {rec['candidate_pool_size']}")
        print(f"Why Chosen: {rec['why_chosen']}\n")

        print("=== 2. Attempt Logging & Demolition Penalty Test ===")
        attempt_res = record_problem_attempt(
            user_id=user.id,
            frontend_question_id=rec["problem_id"],
            time_spent_seconds=600,
            success=True,
            submission_count=1,
            hints_used=0,
            session=session,
        )
        print(f"Attempt Success Logged! Updated Reward: {attempt_res.get('reward', 'N/A')}\n")

        print("=== 3. AI Mock Interview Generation Test ===")
        interview = create_mock_interview(user_id=user.id, session=session)
        print(f"Interview Created! Target Topics: {interview['target_topics']}")
        print(f"Initial AI Greeting:\n{interview['initial_message']}\n")

        print("Pipeline verification completed successfully!")
    finally:
        session.close()

if __name__ == "__main__":
    run_test()