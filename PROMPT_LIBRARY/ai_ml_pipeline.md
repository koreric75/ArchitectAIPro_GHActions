# AI/ML Pipeline Architecture Prompt

Generate a Mermaid.js architecture diagram for an AI/ML-powered application.

## Key Components

1. **API Gateway** (AWS API Gateway or ALB)
2. **Inference API** (FastAPI serving ML models)
3. **Model Registry** (S3 or SageMaker Model Registry)
4. **Training Pipeline** (SageMaker or custom EKS jobs)
5. **Feature Store** (PostgreSQL or Redis)
6. **Monitoring** (CloudWatch, Prometheus/Grafana)
7. **Data Lake** (S3 for raw data ingestion)

## Requirements

- Include a `subgraph Security` boundary with WAF and IAM roles
- Show the training vs. inference paths clearly
- Use the BlueFalconInk LLC primary color `#1E40AF`
- Include data flow arrows for the full ML lifecycle
- Output valid Mermaid.js syntax
