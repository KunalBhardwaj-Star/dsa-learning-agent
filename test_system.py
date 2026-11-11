import os
import sys
import uuid
import unittest
import numpy as np
from datetime import datetime, timezone
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ml.bandit import LinUCB
from app.ml.context_engine import construct_context_vector, compute_decay_factor
from app.ml.reward_engine import compute_composite_reward
from backend.db.database import SessionLocal, engine
from backend.db.models import Base, User, Problem, Topic, UserSkill, Attempt, BanditParam, MockInterview
from backend.db.init_db import init_db
from backend.services.auth_service import register_user, verify_user_otp, login_user
from backend.services.recommendation_service import recommend_next_problem, get_user_context_vector
from backend.services.attempt_service import record_problem_attempt
from backend.services.mock_interview_service import create_mock_interview, generate_socratic_response, complete_mock_interview
from backend.services.leetcode_sync import sync_leetcode_activity
from backend.services.roadmap_service import generate_personalized_roadmap
from backend.main import app


class TestProductionDSALearningAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_linucb_math_stability(self):
        linucb = LinUCB(d=8, alpha=0.25)
        context = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.507, 0.8, 0.95], dtype=np.float64)
        candidate_arms = [1, 2, 3]
        bandit_params = {}

        best_arm, best_score, scores = linucb.select_arm(context, candidate_arms, bandit_params)
        self.assertIn(best_arm, candidate_arms)
        self.assertGreater(best_score, 0.0)

        updated_A, updated_b = linucb.update_arm(arm_id=1, user_context=context, reward=2.5)
        self.assertEqual(updated_A.shape, (8, 8))
        self.assertEqual(updated_b.shape, (8, 1))

        inv_A = np.linalg.inv(updated_A)
        self.assertFalse(np.isnan(inv_A).any())

    def test_02_auth_and_otp_flow(self):
        rnd = uuid.uuid4().hex[:6]
        test_email = f"testuser_{rnd}@example.com"
        test_username = f"testuser_{rnd}"
        # 1. Register User
        res_reg = self.client.post("/auth/register", json={"email": test_email, "username": test_username, "password": "Password123!"})
        self.assertEqual(res_reg.status_code, 200)
        reg_data = res_reg.json()
        self.assertEqual(reg_data["status"], "pending_verification")
        otp_code = reg_data["otp_code"]

        # 2. Verify OTP
        res_ver = self.client.post("/auth/verify-otp", json={"email": test_email, "otp_code": otp_code})
        self.assertEqual(res_ver.status_code, 200)
        ver_data = res_ver.json()
        self.assertEqual(ver_data["status"], "verified")
        self.assertIn("access_token", ver_data)

        # 3. Login User
        res_log = self.client.post("/auth/login", json={"identifier": test_email, "password": "Password123!"})
        self.assertEqual(res_log.status_code, 200)
        log_data = res_log.json()
        self.assertEqual(log_data["status"], "authenticated")
        self.assertIn("access_token", log_data)

    def test_03_starbuggs_real_profile_sync(self):
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(leetcode_handle="starbuggs").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.leetcode_handle, "starbuggs")
            self.assertGreaterEqual(user.total_solved, 500)
            self.assertGreaterEqual(user.easy_solved, 100)

            sync_res = sync_leetcode_activity(username_or_id=user.id, session=session)
            self.assertEqual(sync_res["status"], "success")
            self.assertEqual(sync_res["leetcode_handle"], "starbuggs")
        finally:
            session.close()

    def test_04_recommendation_and_feedback(self):
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(leetcode_handle="starbuggs").first()
            rec = recommend_next_problem(user_id=user.id, session=session)
            self.assertIn("problem_id", rec)
            self.assertIn("why_chosen", rec)

            att = record_problem_attempt(user_id=user.id, frontend_question_id=rec["problem_id"], time_spent_seconds=600, success=True, session=session)
            self.assertEqual(att["status"], "success")
        finally:
            session.close()

    def test_05_mock_interview_and_roadmap(self):
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(leetcode_handle="starbuggs").first()
            
            # Interview
            interview = create_mock_interview(user_id=user.id, target_topics=["DP"], session=session)
            self.assertIn("interview_id", interview)

            comp = complete_mock_interview(interview_id=uuid.UUID(interview["interview_id"]), submitted_code="class Solution:\n    def solve(self): pass", session=session)
            self.assertEqual(comp["status"], "COMPLETED")

            # Roadmap
            rm = generate_personalized_roadmap(user=user, session=session)
            self.assertIn("target_companies", rm)
            self.assertEqual(len(rm["target_companies"]), 5)
        finally:
            session.close()

    def test_06_fastapi_rest_endpoints(self):
        # Health
        res_h = self.client.get("/health")
        self.assertEqual(res_h.status_code, 200)

        # Me endpoint
        res_m = self.client.get("/users/me")
        self.assertEqual(res_m.status_code, 200)
        self.assertIn("leetcode_handle", res_m.json())

        # Next recommendation
        res_r = self.client.post("/recommendations/next")
        self.assertEqual(res_r.status_code, 200)

    def test_07_solved_problems_recommendation_filtering(self):
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(leetcode_handle="starbuggs").first()
            self.assertIsNotNone(user)

            # 1. Fetch recommendation for starbuggs
            rec1 = recommend_next_problem(user_id=user.id, session=session)
            self.assertIn("problem_id", rec1)
            rec_id1 = rec1["problem_id"]

            # Verify that #1 Two Sum (which is marked solved in UserSolvedProblem) is NOT recommended
            self.assertNotEqual(rec_id1, 1, "Solved problem #1 Two Sum must not be recommended!")

            # 2. Mark rec_id1 as solved
            record_problem_attempt(user_id=user.id, frontend_question_id=rec_id1, time_spent_seconds=600, success=True, session=session)

            # 3. Next recommendation must NOT equal rec_id1 or #1
            rec2 = recommend_next_problem(user_id=user.id, session=session)
            self.assertIn("problem_id", rec2)
            self.assertNotEqual(rec2["problem_id"], rec_id1, f"Just-solved problem #{rec_id1} must not be recommended again!")
            self.assertNotEqual(rec2["problem_id"], 1, "Solved problem #1 Two Sum must not be recommended!")
            self.assertFalse(rec2.get("is_solved", True))

            # 4. Attempted-but-failed problem (success=False) remains eligible
            # Pick a problem ID that is NOT in UserSolvedProblem (e.g. 3999)
            unsolved_target_id = 3999
            record_problem_attempt(user_id=user.id, frontend_question_id=unsolved_target_id, time_spent_seconds=300, success=False, session=session)
            
            # Verify unsolved_target_id is NOT in UserSolvedProblem
            from backend.db.models import UserSolvedProblem
            sp = session.query(UserSolvedProblem).filter_by(user_id=user.id, frontend_question_id=unsolved_target_id).first()
            self.assertIsNone(sp, "Failed attempt on unsolved problem must not create UserSolvedProblem entry!")
        finally:
            session.close()

    def test_08_catalog_sync_idempotency_and_updates(self):
        from backend.services.leetcode_sync import sync_leetcode_catalog
        from backend.db.models import Problem, BanditParam
        from unittest.mock import patch

        session = SessionLocal()
        try:
            initial_count = session.query(Problem).count()
            self.assertGreater(initial_count, 0)

            # 1. Repeated sync must not duplicate problems (idempotency)
            sync_res = sync_leetcode_catalog(session)
            self.assertEqual(sync_res["status"], "success")
            new_count = session.query(Problem).count()
            self.assertEqual(initial_count, new_count, "Repeated catalog sync must not duplicate existing problems!")

            # 2. Changed metadata is updated
            # Temporarily modify title of problem #1
            p1 = session.query(Problem).filter_by(frontend_question_id=1).first()
            if p1:
                old_title = p1.title
                p1.title = "Outdated Title"
                session.commit()

                # Sync again - metadata should be updated back
                sync_leetcode_catalog(session)
                p1_refreshed = session.query(Problem).filter_by(frontend_question_id=1).first()
                self.assertEqual(p1_refreshed.title, "Two Sum", "Metadata change on LeetCode source must update local catalog record!")

        finally:
            session.close()

    def test_09_multi_user_solved_isolation_and_no_23_98(self):
        from backend.db.models import User, UserSolvedProblem
        from backend.services.auth_service import hash_password
        session = SessionLocal()
        try:
            user_a_hex = uuid.uuid4().hex[:6]
            user_b_hex = uuid.uuid4().hex[:6]
            pwd_h = hash_password("Password123!")
            user_a = User(username=f"user_a_{user_a_hex}", email=f"user_a_{user_a_hex}@example.com", password_hash=pwd_h, leetcode_handle=f"lc_a_{user_a_hex}")
            user_b = User(username=f"user_b_{user_b_hex}", email=f"user_b_{user_b_hex}@example.com", password_hash=pwd_h, leetcode_handle=f"lc_b_{user_b_hex}")
            session.add_all([user_a, user_b])
            session.flush()

            # Mark 23, 98 solved for A
            sp_a1 = UserSolvedProblem(user_id=user_a.id, frontend_question_id=23, source="TEST")
            sp_a2 = UserSolvedProblem(user_id=user_a.id, frontend_question_id=98, source="TEST")

            # Mark 1, 2 solved for B
            sp_b1 = UserSolvedProblem(user_id=user_b.id, frontend_question_id=1, source="TEST")
            sp_b2 = UserSolvedProblem(user_id=user_b.id, frontend_question_id=2, source="TEST")

            session.add_all([sp_a1, sp_a2, sp_b1, sp_b2])
            session.commit()

            # Recommendation for User A must NEVER recommend #23 or #98
            for _ in range(5):
                rec_a = recommend_next_problem(user_id=user_a.id, session=session)
                self.assertNotIn(rec_a["problem_id"], [23, 98], "User A who solved #23 and #98 must never be recommended #23 or #98!")

            # Recommendation for User B must NEVER recommend #1 or #2, but CAN recommend #23 or #98
            rec_b = recommend_next_problem(user_id=user_b.id, session=session)
            self.assertNotIn(rec_b["problem_id"], [1, 2], "User B who solved #1 and #2 must never be recommended #1 or #2!")

        finally:
            session.close()

    def test_10_failed_sync_does_not_destroy_catalog(self):
        from backend.services.leetcode_sync import sync_leetcode_catalog
        from backend.db.models import Problem
        from unittest.mock import patch, MagicMock

        session = SessionLocal()
        try:
            count_before = session.query(Problem).count()
            self.assertGreater(count_before, 0)

            # Mock a failed API call (HTTP 500)
            mock_resp = MagicMock()
            mock_resp.status_code = 500

            with patch("requests.get", return_value=mock_resp):
                res = sync_leetcode_catalog(session)
                self.assertEqual(res["status"], "failed")

            count_after = session.query(Problem).count()
            self.assertEqual(count_before, count_after, "Failed catalog sync must never delete or wipe existing catalog data!")
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()

