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
    "Design",
]

DIFFICULTIES = [
    "Easy",
    "Medium",
    "Hard",
]

DIFFICULTY_LEVEL = {
    "Easy": 0.25,
    "Medium": 0.55,
    "Hard": 0.85,
}

N_TOPICS = len(TOPICS)
N_DIFFICULTIES = len(DIFFICULTIES)
N_ARMS = N_TOPICS * N_DIFFICULTIES

CONTEXT_DIM = N_TOPICS * 3 + 1