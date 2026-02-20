# Proposal / Document Automation Prompt

Generate a Mermaid.js architecture diagram for an AI-powered proposal
and document automation platform (ProposalBuddyAI).

## Key Components

1. **Web Frontend** (React or Next.js)
2. **Document Ingestion** (S3 upload + text extraction)
3. **AI Analysis Engine** (LLM API integration — OpenAI / Anthropic)
4. **Template Engine** (Jinja2 / DOCX generation)
5. **Compliance Checker** (Rule-based + AI validation)
6. **Database** (PostgreSQL for proposals, metadata, and audit trails)
7. **Export Service** (PDF/DOCX/Markdown generation pipeline)
8. **Notification Service** (SES for email, SNS for alerts)

## Requirements

- Include a `subgraph Security` boundary with WAF and ALB
- Show the full proposal lifecycle: Ingest → Analyze → Generate → Review → Export
- Use the BlueFalconInk LLC primary color `#1E40AF`
- Include audit trail / compliance logging
- Output valid Mermaid.js syntax
