# IMPLEMENTATION RULES

## Rule 1

No feature defined in the SRS may be removed.

If a feature exists in the SRS:

* it must exist in the implementation
* it must be tested
* it must be documented

---

## Rule 2

The SRS is the primary source of truth.

Priority:

1. SRS
2. Markdown Documentation
3. Existing Code

If code conflicts with SRS:

follow the SRS.

---

## Rule 3

Before implementing any feature:

1. Read SRS
2. Read markdown files
3. Inspect current implementation

Generate a gap analysis.

---

## Rule 4

Work in execution loops.

Loop:

Audit
→ Compare
→ Fix
→ Test
→ Re-audit
→ Repeat

until all SRS requirements are satisfied.

---

## Rule 5

Never mark a feature as complete without:

* implementation
* testing
* validation

---

## Rule 6

Generate reports after every cycle.

Report must contain:

### Implemented

List completed features.

### Missing

List missing features.

### Partially Complete

List incomplete features.

### Blockers

List blockers.

### Next Tasks

List next actions.

---

## Rule 7

Database schema must remain aligned with SRS.

Never simplify:

* tables
* foreign keys
* indexes
* enums
* constraints

without explicit documentation.

---

## Rule 8

Maintain production-quality code.

Requirements:

* Type safety
* Validation
* Error handling
* Logging
* Unit tests
* Integration tests
* Documentation

---

## Completion Definition

Project is complete only when:

* All SRS requirements exist
* All APIs work
* All database objects exist
* All tests pass
* Frontend is functional
* Recommendation engine works
* AI interview studio works
* Live LeetCode synchronization works
