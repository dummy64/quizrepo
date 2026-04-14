# ADR-005: Time-Boxed Answer Window with Polling Scorer

**Status:** Accepted  
**Date:** 2026-04-12

## Context

Quizzes need a configurable answer window. After the window closes, scoring must happen and results must be published. Options: (a) schedule a one-off EventBridge event at closes_at time, (b) poll periodically for expired quizzes.

## Decision

Use a polling approach: the Scorer Lambda runs every 15 minutes via EventBridge rate rule and scans for quizzes where `status = active` and `closes_at <= now`.

## Consequences

- **Positive:** Simple implementation — no need to dynamically create/delete EventBridge rules per quiz
- **Positive:** Self-healing — if a scoring run fails, the next run picks it up
- **Positive:** Works for any answer window duration without infrastructure changes
- **Negative:** Up to 15-minute delay between window close and results publishing
- **Negative:** Scan operation on Quizzes table (acceptable given low volume — typically 1 active quiz at a time)
