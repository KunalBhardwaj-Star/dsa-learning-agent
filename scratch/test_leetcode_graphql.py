import requests
import json

url = "https://leetcode.com/graphql"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Content-Type": "application/json"}

query = """
query userProfileUserQuestionProgressV2($userSlug: String!) {
    userProfileUserQuestionProgressV2(userSlug: $userSlug) {
        numAcceptedQuestions {
            count
            difficulty
        }
        numFailedQuestions {
            count
            difficulty
        }
        numUntouchedQuestions {
            count
            difficulty
        }
        userSessionBeatsPercentage {
            difficulty
            percentage
        }
    }
}
"""

print("=== Testing userProfileUserQuestionProgressV2 ===")
resp = requests.post(url, json={"query": query, "variables": {"userSlug": "starbuggs"}}, headers=headers)
print("Status:", resp.status_code)
print(json.dumps(resp.json(), indent=2))
