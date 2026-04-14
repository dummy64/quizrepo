# ADR-002: AWS Bedrock for Quiz Generation

**Status:** Accepted  
**Date:** 2026-04-12

## Context

We need an AI model to generate quiz questions with configurable topics. Options considered: OpenAI GPT API, AWS Bedrock (Claude), self-hosted models.

## Decision

Use AWS Bedrock with Anthropic Claude via the Converse API.

## Consequences

- **Positive:** Stays within the AWS ecosystem — no external API keys to manage, IAM-based auth
- **Positive:** Bedrock handles model hosting, scaling, and availability
- **Positive:** Claude produces high-quality structured JSON output reliably
- **Negative:** Bedrock model access must be explicitly enabled per region
- **Negative:** Slightly higher per-token cost than direct Anthropic API, but simpler operationally
