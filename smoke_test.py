"""
smoke_test.py -- run this from the project root anytime you want a single,
comprehensive report of what's broken, instead of finding out one crash at
a time through the API.

Usage:  python smoke_test.py

What it does NOT do: check your .env / database connection (that needs a
live DB). It only checks that every module in the project actually
imports cleanly -- catches exactly the class of bug we kept hitting
(stale imports, renamed classes, mismatched constructor args) in one pass.
"""

import importlib
import sys
import traceback

# Every module worth checking -- add to this list as the project grows
MODULES_TO_CHECK = [
    "data.constants",
    "data.mappings",
    "data.learners",
    "data.population",
    "data.simulator",
    "bandit.policies.policy",
    "bandit.policies.random_policy",
    "bandit.policies.thompson_sampling_policy",
    "backend.db.connections",
    "backend.db.learner_context",
    "backend.db.learner_repository",
    "backend.db.problem_repository",
    "backend.db.bandit_state_repository",
    "backend.db.db",
    "backend.services.recommendation_service",
    "backend.main",
    "eval.regret_experiment",
    "scripts.cold_start_seed",
]

def main():
    results = []
    for module_name in MODULES_TO_CHECK:
        try:
            importlib.import_module(module_name)
            results.append((module_name, "OK", None))
        except Exception as e:
            results.append((module_name, "FAIL", f"{type(e).__name__}: {e}"))

    print(f"{'MODULE':<45} {'STATUS'}")
    print("-" * 70)
    fail_count = 0
    for module_name, status, error in results:
        marker = "PASS" if status == "OK" else "FAIL"
        print(f"{module_name:<45} {marker}")
        if status == "FAIL":
            fail_count += 1
            print(f"    -> {error}")

    print("-" * 70)
    print(f"{len(results) - fail_count}/{len(results)} modules import cleanly.")

    if fail_count > 0:
        print("\nFix these BEFORE touching the API or running anything else --")
        print("everything downstream of a broken import will fail too, and the")
        print("error you see there often won't point back to the real cause.")
        sys.exit(1)
    else:
        print("\nAll imports clean. Any remaining failures are runtime/data issues")
        print("(DB connection, missing rows, etc.), not structural import problems.")


if __name__ == "__main__":
    main()