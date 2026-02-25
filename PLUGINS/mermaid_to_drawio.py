#!/usr/bin/env python3
"""
Mermaid.js to Draw.io (diagrams.net) Converter

Converts Mermaid.js architecture diagrams to Draw.io XML format
for import into the Draw.io desktop or web application.

Usage:
    python mermaid_to_drawio.py --input docs/architecture.md --output docs/architecture.drawio
"""

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple


def extract_mermaid(content: str) -> str:
    """Extract Mermaid code from a markdown file."""
    pattern = r"```mermaid\s*(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no fenced block, assume the whole content is Mermaid
    return content.strip()


def parse_nodes(mermaid: str) -> List[dict]:
    """Parse node definitions from Mermaid syntax."""
    nodes = []
    # Match patterns like: A[Label], A([Label]), A((Label)), A[(Label)]
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
    # Match patterns like: A --> B, A ==> B, A -.-> B, A -->|label| B
    edge_pattern = r"(\w+)\s*[-=.]+>+\|?([^|]*)\|?\s*(\w+)"
    for match in re.finditer(edge_pattern, mermaid):
        source = match.group(1)
        label = match.group(2).strip()
        target = match.group(3)
        edges.append((source, target, label))
    return edges


def generate_drawio_xml(nodes: List[dict], edges: List[Tuple[str, str, str]]) -> str:
    """Generate Draw.io XML from parsed nodes and edges."""
    root = ET.Element("mxfile")
    diagram = ET.SubElement(root, "diagram", name="Architecture", id="arch-1")
    model = ET.SubElement(diagram, "mxGraphModel")
    cell_root = ET.SubElement(model, "root")

    # Required root cells
    ET.SubElement(cell_root, "mxCell", id="0")
    ET.SubElement(cell_root, "mxCell", id="1", parent="0")

    # Create node cells
    node_map = {}
    for i, node in enumerate(nodes):
        cell_id = str(i + 2)
        node_map[node["id"]] = cell_id
        x = (i % 4) * 200 + 50
        y = (i // 4) * 150 + 50

        cell = ET.SubElement(
            cell_root,
            "mxCell",
            id=cell_id,
            value=node["label"],
            style="rounded=1;whiteSpace=wrap;fillColor=#1E40AF;fontColor=#FFFFFF;strokeColor=#3B82F6;",
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            cell, "mxGeometry", x=str(x), y=str(y), width="160", height="60", **{"as": "geometry"}
        )

    # Create edge cells
    for i, (source, target, label) in enumerate(edges):
        cell_id = str(len(nodes) + i + 2)
        source_id = node_map.get(source, "1")
        target_id = node_map.get(target, "1")

        ET.SubElement(
            cell_root,
            "mxCell",
            id=cell_id,
            value=label,
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;",
            edge="1",
            parent="1",
            source=source_id,
            target=target_id,
        )

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


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
    parser = argparse.ArgumentParser(description="Convert Mermaid.js to Draw.io XML")
    parser.add_argument("--input", required=True, help="Input Mermaid markdown file")
    parser.add_argument("--output", required=True, help="Output Draw.io XML file")
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
    xml_output = generate_drawio_xml(nodes, edges)

    with open(output_path, "w") as f:
        f.write(xml_output)

    print(f"✅ Exported {len(nodes)} nodes and {len(edges)} edges to {output_path}")


if __name__ == "__main__":
    main()
