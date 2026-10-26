# Product Boundaries

**SAIA** is a domain-specific product for structural engineering workflows: chat, engineering agents, file ingestion, document extraction, and project-scoped execution.

**World** is a future, separate platform/product. It may eventually reuse some architectural concepts (Meta-Agent patterns, agent discovery, human approval, agent builder integration), but World is not implemented in this repository and must not be conflated with SAIA.

## Meta-Agent in SAIA

The Meta-Agent foundation in this repository is optional and isolated:

- Invoked only via explicit `/api/v1/meta-agent/*` endpoints
- Not wired into `POST /api/v1/chat`
- Scoped to structural-engineering agent proposals only
- Requires Human Approval before registration
- Registered agents remain DRAFT until the normal publish/approval lifecycle

Do not add World-specific multi-domain behavior, branding, or generic platform features to SAIA.
