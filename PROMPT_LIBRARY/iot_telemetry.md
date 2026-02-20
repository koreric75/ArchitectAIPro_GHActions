# IoT / Telemetry Architecture Prompt

Generate a Mermaid.js architecture diagram for an IoT data platform
(e.g., RC hobby telemetry for Clipstream).

## Key Components

1. **Device Layer** (IoT sensors, RC telemetry transmitters)
2. **Ingestion** (Cloud IoT Core or MQTT broker via Pub/Sub)
3. **Stream Processing** (Cloud Dataflow or Apache Kafka on GKE)
4. **Storage** (Cloud Storage for raw data, Firestore/BigQuery for time-series)
5. **Analytics API** (FastAPI)
6. **Dashboard** (React/Next.js with real-time WebSocket updates)
7. **CDN** (Cloud CDN for dashboard assets)

## Requirements

- Include a `subgraph Security` boundary with device authentication
- Show real-time data flow from device to dashboard
- Use the BlueFalconInk LLC primary color `#1E40AF`
- Include edge computing layer if applicable
- Output valid Mermaid.js syntax
