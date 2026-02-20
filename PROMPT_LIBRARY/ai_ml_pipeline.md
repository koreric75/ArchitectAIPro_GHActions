# AI/ML Pipeline Architecture Prompt

Generate a Mermaid.js architecture diagram for an AI/ML-powered application.

## Key Components

1. **API Gateway** (Cloud Endpoints or Cloud Load Balancer)
2. **Inference API** (FastAPI serving ML models on Cloud Run)
3. **Model Registry** (Vertex AI Model Registry or Cloud Storage)
4. **Training Pipeline** (Vertex AI Training or custom Cloud Run jobs)
5. **Feature Store** (Cloud SQL PostgreSQL or Cloud Memorystore Redis)
6. **Monitoring** (Cloud Monitoring, Prometheus/Grafana)
7. **Data Lake** (Cloud Storage for raw data ingestion)

## Requirements

- Include a `subgraph Security` boundary with Cloud Armor and IAM roles
- Show the training vs. inference paths clearly
- Use the BlueFalconInk LLC primary color `#1E40AF`
- Include data flow arrows for the full ML lifecycle
- Output valid Mermaid.js syntax
