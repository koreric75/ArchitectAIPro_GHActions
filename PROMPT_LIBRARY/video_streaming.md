# Video Streaming / Instructional Site Prompt

Generate a Mermaid.js C4 Context diagram for a subscription-based instructional
video platform (BlueFalconInk LLC). The system serves IT, Cooking, and Music/Instrument lessons.

## Key Components

1. **Web/Mobile Frontend** (Next.js)
2. **Authentication** (Clerk or Firebase Auth)
3. **Subscription Engine** (Stripe Integration)
4. **Video Content API** (FastAPI)
5. **CDN & Storage** (AWS CloudFront & S3 for global low-latency streaming)
6. **Transcoding Pipeline** (AWS MediaConvert for 480p/720p/1080p)
7. **Database** (PostgreSQL for user progress, course metadata, and subscriptions)
8. **Search** (Elasticsearch for course discovery)

## Requirements

- Ensure the diagram uses the BlueFalconInk LLC primary color `#1E40AF`
- Highlight the secure path for paid subscribers (Signed URLs from CloudFront)
- Include DRM/Access Control boundary between public internet and S3 video buckets
- Separate Stripe payment logic in its own `subgraph Payment` for PCI compliance
- Show content delivery path: Upload → Transcode → S3 → CloudFront → Viewer
- Include a `subgraph Security` with WAF and ALB
