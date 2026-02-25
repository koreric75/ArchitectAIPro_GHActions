# 📚 Architect AI Pro — Prompt Library

Domain-specific prompts for generating architecture diagrams across common project types.

## Available Prompts

| File | Domain | Description |
|------|--------|-------------|
| `saas.md` | SaaS Platform | Full-stack SaaS with Stripe, CDN, and security boundaries |
| `video_streaming.md` | Video/Education | Subscription-based video platform with transcoding pipeline |
| `ai_ml_pipeline.md` | AI/ML | ML inference and training pipeline with model registry |
| `iot_telemetry.md` | IoT/Telemetry | IoT device fleet with real-time telemetry ingestion |
| `proposal_automation.md` | Automation | Proposal generation and bid automation workflow |

## Usage

Pass these prompts to the diagram generator along with your `ARCHITECT_CONFIG.json`:

```bash
export GEMINI_API_KEY="your-key-here"

python .github/scripts/generate_diagram.py \
  --config ARCHITECT_CONFIG.json \
  --output docs/architecture.md \
  --scan-dir .
```

The generator automatically selects the best prompt based on the detected project domain. You can also use these prompts as references when customizing your `ARCHITECT_CONFIG.json`.
