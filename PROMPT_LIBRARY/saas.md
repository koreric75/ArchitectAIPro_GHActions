# SaaS Platform Architecture Prompt

Generate a Mermaid.js C4 Context diagram for a SaaS platform with these components:

1. **Web/Mobile Frontend** (Next.js or React SPA)
2. **Authentication** (Clerk, Firebase Auth, or AWS Cognito)
3. **Subscription Engine** (Stripe Integration)
4. **Application API** (FastAPI or GraphQL)
5. **CDN & Storage** (AWS CloudFront & S3 for static assets and media)
6. **Database** (PostgreSQL for application data, Redis for caching)
7. **Message Queue** (Amazon SQS for async processing)

## Requirements

- Include a `subgraph Security` boundary with WAF and ALB
- Separate the `subgraph Payment` boundary for Stripe logic
- Show data flow arrows between all components
- Use the BlueFalconInk LLC primary color `#1E40AF`
- Include CDN in the content delivery path
- Output valid Mermaid.js syntax
