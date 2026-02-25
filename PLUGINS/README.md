# 🔌 Architect AI Pro — Plugins

Converter plugins for exporting Mermaid.js diagrams to other formats.

## Available Plugins

| Plugin | Format | Description |
|--------|--------|-------------|
| `mermaid_to_drawio.py` | Draw.io XML | Converts Mermaid to Draw.io importable XML |
| `mermaid_to_excalidraw.py` | Excalidraw JSON | Converts Mermaid to Excalidraw format |

## Secure Plugin Loading (CSIAC SoftSec)

Plugins are executed through `plugin_loader.py`, which enforces:

- **SHA-256 hash verification** — every plugin is checked against `.plugin_hashes.json` before execution.
- **Path traversal protection** — input/output paths must resolve within the project root.
- **Sandboxed execution** — plugins run in isolated subprocesses with stripped environment variables, enforced timeouts, and captured stdout/stderr.
- **Input size limits** — files larger than 10 MB are rejected.

### Generating / updating hashes

```bash
python PLUGINS/plugin_loader.py --rehash
```

### Verifying plugin integrity

```bash
python PLUGINS/plugin_loader.py --verify
```

### Running a plugin securely

```bash
python PLUGINS/plugin_loader.py --run mermaid_to_drawio.py -- --input docs/architecture.md --output docs/architecture.drawio
```

## Direct Usage (development only)

```bash
python PLUGINS/mermaid_to_drawio.py --input docs/architecture.md --output docs/architecture.drawio
python PLUGINS/mermaid_to_excalidraw.py --input docs/architecture.md --output docs/architecture.excalidraw
```
