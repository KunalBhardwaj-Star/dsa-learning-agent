import requests
import json

url = "https://leetcode.com/graphql"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Content-Type": "application/json"}

query_problemset = """
query problemsetQuestionListV2($categorySlug: String, $limit: Int, $skip: Int) {
    problemsetQuestionListV2(categorySlug: $categorySlug, limit: $limit, skip: $skip) {
        questions {
            id
            title
            titleSlug
            difficulty
        }
    }
}
"""

r1 = requests.post(url, json={"query": query_problemset, "variables": {"categorySlug": "", "limit": 50, "skip": 0}}, headers=headers)
print("Problemset status:", r1.status_code)
if r1.status_code == 200:
    data1 = r1.json()
    questions = data1.get("data", {}).get("problemsetQuestionListV2", {}).get("questions", [])
    print(f"Retrieved {len(questions)} problems.")
    if questions:
        print("Sample question:", questions[0])
