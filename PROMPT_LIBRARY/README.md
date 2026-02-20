# 📚 Architect AI Pro — Prompt Library

Domain-specific prompts for generating architecture diagrams across common project types.

## Usage

Pass these prompts to Architect AI Pro along with your `ARCHITECT_CONFIG.json` to generate
standardized, compliant architecture diagrams.

```bash
architect-ai generate . \
  --prompt PROMPT_LIBRARY/saas.md \
  --config ARCHITECT_CONFIG.json \
  --output docs/architecture.md
```
