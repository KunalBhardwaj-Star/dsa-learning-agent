import requests
import json

def fetch_starbuggs():
    url = "https://leetcode.com/graphql"
    query = """
    query userPublicProfile($username: String!) {
        matchedUser(username: $username) {
            username
            githubUrl
            twitterUrl
            submitStats {
                acSubmissionNum {
                    difficulty
                    count
                }
                totalSubmissionNum {
                    difficulty
                    count
                }
            }
            profile {
                ranking
                reputation
                userAvatar
                realName
            }
            tagProblemCounts {
                fundamental {
                    tagName
                    tagSlug
                    problemsSolved
                }
                intermediate {
                    tagName
                    tagSlug
                    problemsSolved
                }
                advanced {
                    tagName
                    tagSlug
                    problemsSolved
                }
            }
        }
        recentSubmissionList(username: $username, limit: 20) {
            title
            titleSlug
            timestamp
            statusDisplay
            lang
            memory
            runtime
        }
        userContestRanking(username: $username) {
            rating
            globalRanking
            topPercentage
            totalParticipants
        }
    }
    """
    resp = requests.post(
        url,
        json={"query": query, "variables": {"username": "starbuggs"}},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        timeout=10
    )
    print("Status code:", resp.status_code)
    data = resp.json()
    print(json.dumps(data, indent=2))
    return data

if __name__ == "__main__":
    fetch_starbuggs()
