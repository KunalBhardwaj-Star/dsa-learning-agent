import json

TAG_TO_TOPIC = {
    # Arrays
    "array": "Arrays",
    "matrix": "Arrays",
    "simulation": "Arrays",
    "enumeration": "Arrays",
    "sorting": "Arrays",
    "two-pointers": "Arrays",
    "sliding-window": "Arrays",
    "quickselect": "Arrays",

    # Strings
    "string": "Strings",
    "rolling-hash": "Strings",

    # Linked List
    "linked-list": "LinkedList",

    # Stack
    "stack": "Stack",
    "monotonic-stack": "Stack",

    # Queue
    "queue": "Queue",
    "monotonic-queue": "Queue",

    # Hashing
    "hash-table": "Hashing",

    # Binary Search
    "binary-search": "BinarySearch",

    # Trees
    "tree": "Trees",
    "binary-tree": "Trees",
    "segment-tree": "Trees",
    "binary-indexed-tree": "Trees",
    "ordered-set": "Trees",

    # Trie
    "trie": "Trie",

    # Heap
    "heap-priority-queue": "Heap",

    # Graphs
    "graph": "Graphs",
    "depth-first-search": "Graphs",
    "breadth-first-search": "Graphs",
    "topological-sort": "Graphs",
    "shortest-path": "Graphs",

    # Union Find
    "union-find": "UnionFind",

    # DP
    "dynamic-programming": "DP",
    "game-theory": "DP",

    # Greedy
    "greedy": "Greedy",

    # Backtracking
    "backtracking": "Backtracking",
    "recursion": "Backtracking",
    "divide-and-conquer": "Backtracking",

    # Bit Manipulation
    "bit-manipulation": "BitManipulation",
    "bitmask": "BitManipulation",

    # Math
    "math": "Math",
    "randomized": "Math",
    "brainteaser": "Math",
    "sweep-line": "Math",

    # Optional extra category
    "design": "Design",
    "iterator": "Design",
    "data-stream": "Design",
}

TOPICS = [
    "Arrays",
    "Strings",
    "LinkedList",
    "Stack",
    "Queue",
    "Hashing",
    "BinarySearch",
    "Trees",
    "Trie",
    "Heap",
    "Graphs",
    "UnionFind",
    "DP",
    "Greedy",
    "Backtracking",
    "BitManipulation",
    "Math",
    "Design"
]

def load_data(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_topic_exposure(data: dict) -> dict:
    exposure = {topic: 0 for topic in TOPICS}

    tag_counts = data["data"]["matchedUser"]["tagProblemCounts"]

    for level in ["fundamental", "intermediate", "advanced"]:
        for tag in tag_counts[level]:
            slug = tag["tagSlug"]
            solved = tag["problemsSolved"]

            topic = TAG_TO_TOPIC.get(slug)
            if topic:
                exposure[topic] += solved
            else:
                print(f"Unknown tag: {slug}")

    return exposure


def compute_recent_accuracy(data: dict) -> float:
    submissions = data["data"]["recentSubmissionList"]

    if len(submissions) == 0:
        return 0.0

    accepted = sum(
        1
        for submission in submissions
        if submission["statusDisplay"] == "Accepted"
    )

    return accepted / len(submissions)


if __name__ == "__main__":
    data = load_data("leetcode_data.json")
    exposure = compute_topic_exposure(data)
    accuracy = compute_recent_accuracy(data)

    print("Topic exposure (solved-count proxy):")
    for topic, count in exposure.items():
        print(f"  {topic}: {count}")
    print(f"\nRecent accuracy (last 20 submissions): {accuracy:.2f}")