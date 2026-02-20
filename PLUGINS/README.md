# 🔌 Architect AI Pro — Plugins

Converter plugins for exporting Mermaid.js diagrams to other formats.

## Available Plugins

| Plugin | Format | Description |
|--------|--------|-------------|
| `mermaid_to_drawio.py` | Draw.io XML | Converts Mermaid to Draw.io importable XML |
| `mermaid_to_excalidraw.py` | Excalidraw JSON | Converts Mermaid to Excalidraw format |

## Usage

```bash
python PLUGINS/mermaid_to_drawio.py --input docs/architecture.md --output docs/architecture.drawio
python PLUGINS/mermaid_to_excalidraw.py --input docs/architecture.md --output docs/architecture.excalidraw
```
