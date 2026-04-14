# ADR-003: Dual Platform Support (Slack + Teams)

**Status:** Accepted  
**Date:** 2026-04-12

## Context

Entain India uses both Slack and Microsoft Teams. The quiz system must reach all employees regardless of which platform they use.

## Decision

Support both platforms with native interactive experiences: Slack Block Kit for Slack, Adaptive Cards for Teams. Both share the same backend answer collection and scoring logic.

## Consequences

- **Positive:** Maximum reach across the organization
- **Positive:** Native UX on each platform (not a lowest-common-denominator approach)
- **Positive:** Shared answer collector means consistent scoring regardless of platform
- **Negative:** Two bot integrations to maintain (Slack app + Teams webhook)
- **Negative:** Different interaction models require platform-specific handler code
