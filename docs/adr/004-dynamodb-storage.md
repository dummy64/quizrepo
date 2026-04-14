# ADR-004: DynamoDB for Data Storage

**Status:** Accepted  
**Date:** 2026-04-12

## Context

We need to store quizzes, user responses, leaderboard data, and configuration. Access patterns are well-defined: lookup by quiz_id, query responses by quiz_id + user_id, leaderboard sorted by score.

## Decision

Use DynamoDB with PAY_PER_REQUEST billing and four tables: Quizzes, Responses, Leaderboard (with a Local Secondary Index on score), and Config.

## Consequences

- **Positive:** Serverless, auto-scaling, no capacity planning needed
- **Positive:** Single-digit millisecond latency for all access patterns
- **Positive:** PAY_PER_REQUEST is cost-effective for bursty daily quiz traffic
- **Positive:** LSI on Leaderboard enables efficient top-N queries by score
- **Negative:** No complex queries or joins — but our access patterns don't need them
- **Negative:** Scan operations in the scorer (finding active quizzes) are acceptable given low quiz volume
