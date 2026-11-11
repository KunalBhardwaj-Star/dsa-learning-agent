import requests
import json

# Test fetching complete problem catalog from LeetCode REST endpoint
url_rest = "https://leetcode.com/api/problems/all/"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

print("=== Testing LeetCode REST Endpoint https://leetcode.com/api/problems/all/ ===")
try:
    resp = requests.get(url_rest, headers=headers, timeout=10)
    print("Status:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        stat_pairs = data.get("stat_status_pairs", [])
        print(f"Total problems returned by REST API: {len(stat_pairs)}")
        if stat_pairs:
            sample = stat_pairs[0]
            print("Sample item:", {
                "question_id": sample.get("stat", {}).get("question_id"),
                "frontend_question_id": sample.get("stat", {}).get("frontend_question_id"),
                "title": sample.get("stat", {}).get("question__title"),
                "title_slug": sample.get("stat", {}).get("question__title_slug"),
                "difficulty_level": sample.get("difficulty", {}).get("level"),
                "paid_only": sample.get("paid_only")
            })
except Exception as e:
    print("Error:", e)
