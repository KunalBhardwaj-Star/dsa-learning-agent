import requests
import json

url = "https://leetcode.com/graphql"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Content-Type": "application/json"}

query = """
query {
    userProgressQuestionList {
        totalNum
        questions {
            title
            titleSlug
            questionStatus
            frontendId
        }
    }
}
"""

print("=== Testing userProgressQuestionList without args ===")
r = requests.post(url, json={"query": query}, headers=headers)
print("Status:", r.status_code)
try:
    data = r.json()
    print(json.dumps(data, indent=2)[:800])
except Exception as e:
    print(r.text[:800])
