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

    # Design
    "design": "Design",
    "iterator": "Design",
    "data-stream": "Design",
}


def map_all_topics(topic_tags: list[dict]) -> list[str]:
    """
    Returns all mapped topics for a problem.
    Duplicate topics are removed.
    """

    topics = []

    for tag in topic_tags:
        topic = TAG_TO_TOPIC.get(tag["slug"])

        if topic and topic not in topics:
            topics.append(topic)

    return topics