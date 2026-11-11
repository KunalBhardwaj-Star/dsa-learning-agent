import requests

QUERY = """
query problemsetQuestionList(
  $categorySlug: String,
  $limit: Int,
  $skip: Int,
  $filters: QuestionListFilterInput
) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    total: totalNum
    questions: data {
      difficulty
      title
      titleSlug
      frontendQuestionId: questionFrontendId
      paidOnly: isPaidOnly
      topicTags {
        slug
      }
    }
  }
}
"""


def fetch_problems(limit: int = 100, skip: int = 0) -> list[dict]:
    response = requests.post(
        "https://leetcode.com/graphql",
        json={
            "query": QUERY,
            "variables": {
                "categorySlug": "",
                "skip": skip,
                "limit": limit,
                "filters": {}
            }
        },
        headers={
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com"
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()["data"]["problemsetQuestionList"]["questions"]

def fetch_all_problems():
    all_problems = []
    skip = 0
    limit = 500

    while True:
        batch = fetch_problems(limit=100, skip=skip)

        print(
            f"skip={skip}, fetched={len(batch)}"
        )

        if not batch:
            break

        all_problems.extend(batch)
        skip += 100
    return all_problems