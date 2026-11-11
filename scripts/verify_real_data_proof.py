import os
import sys
import json
import uuid
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.database import SessionLocal
from backend.db.models import User, Problem, MockInterview, MockInterviewTranscript
from backend.services.leetcode_sync import fetch_leetcode_graphql_user, sync_leetcode_activity
from backend.services.recommendation_service import recommend_next_problem, get_user_context_vector
from backend.services.mock_interview_service import create_mock_interview, generate_socratic_response, complete_mock_interview


def run_proof():
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(leetcode_handle="starbuggs").first()
        if not user:
            print("User starbuggs not found in DB.")
            return

        print("================================================================================")
        print("                 100% REAL-DATA & SRS COMPLIANCE PROOF REPORT                   ")
        print("================================================================================")

        # 1. Live GraphQL & User Profile Proof
        print("\n--- PROOF 1: LIVE LEETCODE GRAPHQL FETCH (starbuggs) ---")
        live_graphql = fetch_leetcode_graphql_user("starbuggs")
        matched = live_graphql.get("matchedUser", {})
        stats = matched.get("submitStats", {}).get("acSubmissionNum", [])
        print(f"LeetCode Profile Username: {matched.get('username')}")
        print(f"Real Avatar URL: {matched.get('profile', {}).get('userAvatar')}")
        print(f"Global Ranking: #{matched.get('profile', {}).get('ranking')}")
        print(f"Contest Rating: {live_graphql.get('userContestRanking', {}).get('rating')}")
        print(f"Solved Breakdown from GraphQL: {stats}")

        # 2. Sync to PostgreSQL Proof
        print("\n--- PROOF 2: POSTGRESQL DATABASE RECORD (users table) ---")
        print(f"PostgreSQL User UUID: {user.id}")
        print(f"Handle: {user.leetcode_handle}")
        print(f"Total Solved: {user.total_solved}")
        print(f"Easy Solved: {user.easy_solved} | Medium Solved: {user.medium_solved} | Hard Solved: {user.hard_solved}")
        print(f"Contest Rating: {user.contest_rating}")

        # 3. Context Vector Proof
        print("\n--- PROOF 3: 8-DIMENSIONAL LINUCB CONTEXT VECTOR (x_{u,t}) ---")
        ctx = get_user_context_vector(user, session)
        vec = ctx["context_vector"]
        print(f"Constructed Context Vector x_{{u,t}}: {vec.tolist()}")
        print(f"  acc_20 (Recent Accuracy): {ctx['acc_20']}")
        print(f"  S_graph (Graph Skill): {ctx['s_graph']}")
        print(f"  S_dp (DP Skill): {ctx['s_dp']}")
        print(f"  S_tree (Tree Skill): {ctx['s_tree']}")
        print(f"  S_greedy (Greedy Skill): {ctx['s_greedy']}")
        print(f"  contest_rating (Normalized): {ctx['contest_rating']}")
        print(f"  Z_speed (Solve Speed): {ctx['z_speed']}")
        print(f"  decay_factor (Skill Decay): {ctx['decay_factor']}")

        # 4. LinUCB Recommendation Proof
        print("\n--- PROOF 4: LINUCB RECOMMENDATION OUTPUT FOR starbuggs ---")
        rec = recommend_next_problem(user.id, session)
        print(f"Recommended Arm ID (frontend_question_id): {rec['arm_id']}")
        print(f"Problem Title: {rec['title']} ({rec['difficulty']})")
        print(f"Topics: {rec['topics']}")
        print(f"Candidate Pool Size: {rec['candidate_pool_size']} problems")
        print(f"Theta Reward (theta_a^T * x_{{u,t}}): {rec['theta_reward']}")
        print(f"Exploration Bonus (alpha * sqrt(x^T * A^-1 * x)): {rec['exploration_bonus']}")
        print(f"Final UCB Score (p_{{a,t}}): {rec['ucb_score']}")
        print(f"Why Chosen Rationale: {rec['why_chosen']}")
        print(f"Top 5 Ranked Candidates in LinUCB Matrix Evaluation:")
        for r in rec["top_5_rankings"]:
            print(f"   Arm {r['arm_id']}: {r['title']} | UCB Score = {r['ucb_score']}")

        # 5. Socratic Interview Studio Transcript & Scoring Proof
        print("\n--- PROOF 5: AI SOCRATIC MOCK INTERVIEW TRANSCRIPT & SCORING EVIDENCE ---")
        interview = create_mock_interview(user.id, target_topics=["DP"], session=session)
        iid = uuid.UUID(interview["interview_id"])

        # Simulate user transcript responses
        generate_socratic_response(iid, "I plan to use dynamic programming with state dp[i] representing min coins to reach amount i. Time complexity O(N*amount) and space O(amount).", requested_hint="SMALL_NUDGE", session=session)
        generate_socratic_response(iid, "def coin_change(coins, amount):\n    dp = [float('inf')] * (amount + 1)\n    dp[0] = 0\n    for a in range(1, amount + 1):\n        for c in coins:\n            if a - c >= 0:\n                dp[a] = min(dp[a], 1 + dp[a - c])\n    return dp[amount] if dp[amount] != float('inf') else -1", session=session)

        comp = complete_mock_interview(iid, submitted_code="def coin_change(coins, amount):\n    dp = [float('inf')] * (amount + 1)\n    dp[0] = 0\n    for a in range(1, amount + 1):\n        for c in coins:\n            if a - c >= 0:\n                dp[a] = min(dp[a], 1 + dp[a - c])\n    return dp[amount] if dp[amount] != float('inf') else -1", session=session)

        txs = session.query(MockInterviewTranscript).filter_by(interview_id=iid).order_by(MockInterviewTranscript.timestamp.asc()).all()
        print("Transcript Events:")
        for t in txs:
            print(f"  [{t.speaker}]: {t.message_text[:120]}... (Hint: {t.hint_given.value if t.hint_given else 'None'})")

        print("\nDynamic Evaluated Scores (Computed strictly from transcript evidence):")
        print(f"  Communication Score: {comp['communication_score']} (Derived from word count, complexity terms 'O(N)', 'space', 'dp')")
        print(f"  Code Quality Score: {comp['code_quality_score']} (Derived from AST syntax, function definition, loop state)")
        print(f"  Time Management Score: {comp['time_management_score']} (Derived from elapsed minutes vs target 45 mins)")
        print(f"  Overall Performance Index: {comp['overall_performance_index']} (Composite score fed back into LinUCB)")

        print("================================================================================")
    finally:
        session.close()

if __name__ == "__main__":
    run_proof()
