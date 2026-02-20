# SaaS Platform Architecture Prompt

Generate a Mermaid.js C4 Context diagram for a SaaS platform with these components:

1. **Web/Mobile Frontend** (Next.js or React SPA)
2. **Authentication** (Firebase Auth or Identity Platform)
3. **Subscription Engine** (Stripe Integration)
4. **Application API** (FastAPI or GraphQL)
5. **CDN & Storage** (Cloud CDN & Cloud Storage for static assets and media)
6. **Database** (Cloud SQL PostgreSQL for application data, Cloud Memorystore Redis for caching)
7. **Message Queue** (Cloud Pub/Sub for async processing)

## Requirements

- Include a `subgraph Security` boundary with Cloud Armor and Load Balancer
- Separate the `subgraph Payment` boundary for Stripe logic
- Show data flow arrows between all components
- Use the BlueFalconInk LLC primary color `#1E40AF`
- Include CDN in the content delivery path
- Output valid Mermaid.js syntax
