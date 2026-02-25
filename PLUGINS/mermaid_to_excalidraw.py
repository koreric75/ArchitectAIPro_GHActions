#!/usr/bin/env python3
"""
Mermaid.js to Excalidraw Converter

Converts Mermaid.js architecture diagrams to Excalidraw JSON format
for import into Excalidraw.

Usage:
    python mermaid_to_excalidraw.py --input docs/architecture.md --output docs/architecture.excalidraw
"""

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import List, Tuple


def extract_mermaid(content: str) -> str:
    """Extract Mermaid code from a markdown file."""
    pattern = r"```mermaid\s*(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip()


def parse_nodes(mermaid: str) -> List[dict]:
    """Parse node definitions from Mermaid syntax."""
    nodes = []
    node_pattern = r"(\w+)\s*[\[\(\{][\[\(\{]?\s*(.+?)\s*[\]\)\}][\]\)\}]?"
    for match in re.finditer(node_pattern, mermaid):
        node_id = match.group(1)
        label = match.group(2).strip('"\'')
        if node_id not in [n["id"] for n in nodes]:
            nodes.append({"id": node_id, "label": label})
    return nodes


def parse_edges(mermaid: str) -> List[Tuple[str, str, str]]:
    """Parse edge connections from Mermaid syntax."""
    edges = []
    edge_pattern = r"(\w+)\s*[-=.]+>+\|?([^|]*)\|?\s*(\w+)"
    for match in re.finditer(edge_pattern, mermaid):
        source = match.group(1)
        label = match.group(2).strip()
        target = match.group(3)
        edges.append((source, target, label))
    return edges


def generate_excalidraw(nodes: List[dict], edges: List[Tuple[str, str, str]]) -> dict:
    """Generate Excalidraw JSON from parsed nodes and edges."""
    elements = []
    node_positions = {}

    # BlueFalconInk LLC colors
    PRIMARY = "#1E40AF"
    BG = "#BFDBFE"

    # Create rectangle elements for nodes
    for i, node in enumerate(nodes):
        x = (i % 4) * 250 + 50
        y = (i // 4) * 200 + 50
        elem_id = str(uuid.uuid4())[:8]
        node_positions[node["id"]] = {
            "id": elem_id,
            "x": x,
            "y": y,
            "width": 180,
            "height": 70,
        }

        # Rectangle element
        elements.append(
            {
                "type": "rectangle",
                "id": elem_id,
                "x": x,
                "y": y,
                "width": 180,
                "height": 70,
                "strokeColor": PRIMARY,
                "backgroundColor": BG,
                "fillStyle": "solid",
                "strokeWidth": 2,
                "roughness": 1,
                "opacity": 100,
                "roundness": {"type": 3},
            }
        )

        # Text label
        elements.append(
            {
                "type": "text",
                "id": str(uuid.uuid4())[:8],
                "x": x + 10,
                "y": y + 20,
                "width": 160,
                "height": 30,
                "text": node["label"],
                "fontSize": 16,
                "fontFamily": 1,
                "textAlign": "center",
                "verticalAlign": "middle",
                "strokeColor": "#1E293B",
                "containerId": elem_id,
            }
        )

    # Create arrow elements for edges
    for source, target, label in edges:
        if source in node_positions and target in node_positions:
            src = node_positions[source]
            tgt = node_positions[target]

            elements.append(
                {
                    "type": "arrow",
                    "id": str(uuid.uuid4())[:8],
                    "x": src["x"] + src["width"],
                    "y": src["y"] + src["height"] // 2,
                    "width": tgt["x"] - (src["x"] + src["width"]),
                    "height": tgt["y"] - src["y"],
                    "strokeColor": PRIMARY,
                    "strokeWidth": 2,
                    "startBinding": {"elementId": src["id"], "focus": 0, "gap": 5},
                    "endBinding": {"elementId": tgt["id"], "focus": 0, "gap": 5},
                    "points": [
                        [0, 0],
                        [
                            tgt["x"] - (src["x"] + src["width"]),
                            tgt["y"] + tgt["height"] // 2 - (src["y"] + src["height"] // 2),
                        ],
                    ],
                }
            )

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "architect-ai-pro",
        "elements": elements,
        "appState": {
            "viewBackgroundColor": "#0F172A",
            "gridSize": 20,
        },
    }


# ---------------------------------------------------------------------------
# Security: path traversal protection & input size limits
# ---------------------------------------------------------------------------
MAX_INPUT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _validate_path(p: str, label: str) -> Path:
    """Ensure *p* resolves inside PROJECT_ROOT (no traversal)."""
    resolved = Path(p).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        raise SystemExit(f"❌ {label} path '{p}' resolves outside the project root.")
    return resolved


def main():
    parser = argparse.ArgumentParser(description="Convert Mermaid.js to Excalidraw JSON")
    parser.add_argument("--input", required=True, help="Input Mermaid markdown file")
    parser.add_argument("--output", required=True, help="Output Excalidraw JSON file")
    args = parser.parse_args()

    input_path = _validate_path(args.input, "Input")
    output_path = _validate_path(args.output, "Output")

    if input_path.stat().st_size > MAX_INPUT_SIZE_BYTES:
        raise SystemExit(f"❌ Input file exceeds {MAX_INPUT_SIZE_BYTES // (1024*1024)} MB limit.")

    with open(input_path, "r") as f:
        content = f.read()

    mermaid = extract_mermaid(content)
    nodes = parse_nodes(mermaid)
    edges = parse_edges(mermaid)
    excalidraw = generate_excalidraw(nodes, edges)

    with open(output_path, "w") as f:
        json.dump(excalidraw, f, indent=2)

    print(f"✅ Exported {len(nodes)} nodes and {len(edges)} edges to {output_path}")


if __name__ == "__main__":
    main()
