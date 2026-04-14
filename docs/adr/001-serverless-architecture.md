# ADR-001: Serverless Architecture on AWS

**Status:** Accepted  
**Date:** 2026-04-12

## Context

We need to build a daily quiz system for ~1000+ employees. The system runs on a schedule (once or a few times per day) with bursty traffic during the answer window. We need to minimize operational overhead.

## Decision

Use a fully serverless architecture: AWS Lambda for compute, DynamoDB for storage, EventBridge for scheduling, API Gateway for HTTP endpoints.

## Consequences

- **Positive:** Zero server management, automatic scaling to 1000+ concurrent users, pay-per-use pricing (very low cost for a daily quiz), no idle costs
- **Positive:** CDK enables infrastructure-as-code with type safety
- **Negative:** Cold start latency on Lambda (mitigated by low latency requirements — quiz posting is async)
- **Negative:** 15-minute maximum Lambda timeout (sufficient for all our operations)
