import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# 1. Login user
res_login = client.post("/auth/login", json={
    "identifier": input("Enter your login username or email: "),
    "password": input("Enter your password: ")
})
print("Login status:", res_login.status_code)
if res_login.status_code == 200:
    token = res_login.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Call sync-audit endpoint
    res_audit = client.get("/users/me/sync-audit", headers=headers)
    print("Sync audit status:", res_audit.status_code)
    print("Sync audit response:", res_audit.json())
