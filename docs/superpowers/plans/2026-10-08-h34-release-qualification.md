# H3/H4 Release Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one locally qualified, reviewable H3/H4 commit pair without deploying.

**Architecture:** Preserve both source histories on actual origin/main. Join Alembic siblings with an additive no-op merge and exercise the combined contracts against an owned PostgreSQL16 instance. Serial verification limits resource contention.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL16, Next14/React, Vitest, native workerd.

**Spec:** ../specs/2026-10-08-h34-release-qualification.md

## Global Constraints

Root alone merges/deploys; no production writes or provider calls. Preserve PR76/93, migration IDs e1/f1/a8, protected binding a4948e93-2fcd-41fb-ba98-1d693c445c34 and deleted folder e4cd651e-fcf9-491d-86cd-d55a9a37615b. No Engine/Parts expansion. API timing-v2 before H3 Worker; Worker metadata before owner apply.

## Review Focus

- Migrated historical unknown/test bytes must never gain natural status.
- Completed reviews remain readable through authority outage with zero redispatch.
- Owner apply compares fresh card/board/brand; staff access rights remain intact.
- Known/conflicting assignment stops Handin before upload despite optional503.
- Current request route retains version-bound feedback and guest isolation.

### Task1: Compose and join schema

Files: apps/api/alembic/versions/b8d8a10b2026_merge_timing_and_staff_brand.py; apps/api/tests/test_whop_migration.py; release evidence migration-roundtrip.py.

- [ ] Preserve source histories and record actual main bases.
- [ ] Change graph regression to require one b8 head joining f1/a8; run and retain RED.
- [ ] Add no-op b8 merge; verify graph GREEN.
- [ ] Exercise base→head→parents→head and base roundtrip on owned PG with seeded durable rows, compare preserved IDs/data and exclusions.

### Task2: Qualify combined behavior

Files: existing API brand/auth/timing/actual-worker PG tests; existing Worker timing-authority-runtime tests; existing Web Handin and request tests.

- [ ] Run focused regressions plus actual Worker→privateHTTP→PG disconnect/recovery.
- [ ] Run full API with all dedicated PG opt-ins; then Web test/build/types/lint; then Worker serial suite/bundle/types baseline comparison.
- [ ] Retain all unsuccessful attempts and fix only demonstrated integration regressions.

### Task3: Browser and release handoff

Files: local fixture evidence, release/rollback manifest, qualification report, H4.json.

- [ ] Exercise actual current /r and Handin via existing local fixtures; capture current screens and state exact simulated boundaries.
- [ ] Review integration diff and evidence independently, fingerprint exact commits.
- [ ] Record release ordering and rollback limits, no historical redispatch/natural promotion, source preservation and cleanup. Commit exact combined pair and hand off through shared artifacts.
