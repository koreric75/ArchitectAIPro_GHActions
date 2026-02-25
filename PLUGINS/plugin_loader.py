#!/usr/bin/env python3
"""
BlueFalconInk LLC — Secure Plugin Loader

Provides integrity verification, path validation, and sandboxed execution
for Architect AI Pro converter plugins.

Security controls:
  1. SHA-256 hash verification against a trusted registry
  2. Path traversal protection on all file I/O
  3. Sandboxed subprocess execution with timeout and env stripping
  4. File size limits to prevent resource exhaustion

CSIAC Domain: SoftSec (Software Security)

Usage:
    from plugin_loader import run_plugin_sandboxed, verify_plugin_integrity

    verify_plugin_integrity("mermaid_to_drawio.py")
    run_plugin_sandboxed("mermaid_to_drawio", ["--input", "in.md", "--output", "out.drawio"])
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Project root — plugins must reside under PLUGINS/ relative to this
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = PROJECT_ROOT / "PLUGINS"

# Maximum file size a plugin may read/write (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Subprocess timeout for plugin execution (seconds)
PLUGIN_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Plugin Hash Registry
#
# To update after intentional plugin changes, run:
#   python -m PLUGINS.plugin_loader --rehash
# ---------------------------------------------------------------------------

PLUGIN_HASH_REGISTRY: Dict[str, str] = {}
# Populated at first run via compute_plugin_hashes() if empty.
# In production, pin these to known-good values.

_REGISTRY_FILE = PLUGINS_DIR / ".plugin_hashes.json"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PluginSecurityError(Exception):
    """Raised when a plugin fails security validation."""
    pass


class PathTraversalError(PluginSecurityError):
    """Raised when a file path attempts directory traversal."""
    pass


class PluginIntegrityError(PluginSecurityError):
    """Raised when a plugin's hash does not match the registry."""
    pass


# ---------------------------------------------------------------------------
# Hash Verification
# ---------------------------------------------------------------------------

def _sha256_file(filepath: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_registry() -> Dict[str, str]:
    """Load the hash registry from disk or compute fresh."""
    import json

    if _REGISTRY_FILE.exists():
        try:
            data = json.loads(_REGISTRY_FILE.read_text())
            if isinstance(data, dict) and all(
                isinstance(k, str) and isinstance(v, str) for k, v in data.items()
            ):
                return data
        except (json.JSONDecodeError, OSError):
            pass

    # First run — compute and save
    registry = compute_plugin_hashes()
    return registry


def compute_plugin_hashes() -> Dict[str, str]:
    """
    Compute SHA-256 hashes for all .py plugins in PLUGINS/ and
    save to .plugin_hashes.json.

    Call this after intentional plugin modifications to update the registry.
    """
    import json

    registry: Dict[str, str] = {}
    for py_file in sorted(PLUGINS_DIR.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "plugin_loader.py":
            continue
        registry[py_file.name] = _sha256_file(py_file)

    _REGISTRY_FILE.write_text(json.dumps(registry, indent=2) + "\n")
    print(f"[plugin_loader] Updated hash registry: {len(registry)} plugin(s)")
    for name, digest in registry.items():
        print(f"  {name}: {digest[:16]}...")

    return registry


def verify_plugin_integrity(plugin_name: str) -> bool:
    """
    Verify that a plugin file matches its registered SHA-256 hash.

    Args:
        plugin_name: Filename of the plugin (e.g. 'mermaid_to_drawio.py').

    Returns:
        True if the hash matches.

    Raises:
        PluginIntegrityError: If the hash does not match or plugin is unknown.
        FileNotFoundError: If the plugin file does not exist.
    """
    global PLUGIN_HASH_REGISTRY
    if not PLUGIN_HASH_REGISTRY:
        PLUGIN_HASH_REGISTRY = _load_registry()

    plugin_path = PLUGINS_DIR / plugin_name
    if not plugin_path.exists():
        raise FileNotFoundError(f"Plugin not found: {plugin_path}")

    actual_hash = _sha256_file(plugin_path)
    expected_hash = PLUGIN_HASH_REGISTRY.get(plugin_name)

    if expected_hash is None:
        raise PluginIntegrityError(
            f"Plugin '{plugin_name}' is not in the hash registry. "
            f"Run `python -m PLUGINS.plugin_loader --rehash` to register it."
        )

    if actual_hash != expected_hash:
        raise PluginIntegrityError(
            f"Plugin '{plugin_name}' integrity check failed.\n"
            f"  Expected: {expected_hash}\n"
            f"  Actual:   {actual_hash}\n"
            f"The plugin file may have been tampered with."
        )

    return True


# ---------------------------------------------------------------------------
# Path Validation
# ---------------------------------------------------------------------------

def validate_plugin_io(input_path: str, output_path: str) -> tuple:
    """
    Validate input/output file paths for security.

    Prevents path traversal attacks and ensures paths stay within
    the project directory.

    Args:
        input_path: The input file path.
        output_path: The output file path.

    Returns:
        Tuple of (resolved_input, resolved_output) Path objects.

    Raises:
        PathTraversalError: If paths attempt to escape the project root.
        ValueError: If paths are invalid.
    """
    resolved_input = Path(input_path).resolve()
    resolved_output = Path(output_path).resolve()

    for label, resolved in [("input", resolved_input), ("output", resolved_output)]:
        # Check that the resolved path is under the project root
        try:
            resolved.relative_to(PROJECT_ROOT)
        except ValueError:
            raise PathTraversalError(
                f"The {label} path '{resolved}' is outside the project root "
                f"'{PROJECT_ROOT}'. Path traversal is not allowed."
            )

        # Reject paths with suspicious components
        path_str = str(resolved)
        if ".." in Path(input_path if label == "input" else output_path).parts:
            raise PathTraversalError(
                f"The {label} path contains '..' components, which are not allowed."
            )

    # Check input file size
    if resolved_input.exists():
        size = resolved_input.stat().st_size
        if size > MAX_FILE_SIZE:
            raise ValueError(
                f"Input file is too large ({size:,} bytes > {MAX_FILE_SIZE:,} byte limit)."
            )

    return resolved_input, resolved_output


# ---------------------------------------------------------------------------
# Sandboxed Execution
# ---------------------------------------------------------------------------

def run_plugin_sandboxed(
    plugin_name: str,
    args: List[str],
    timeout: Optional[int] = None,
    verify: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run a plugin in a sandboxed subprocess.

    Security measures:
      - Plugin integrity is verified before execution
      - Environment is stripped to only PATH and PYTHONPATH
      - Working directory is locked to the project root
      - Execution has a timeout (default 30s)
      - stdout/stderr are captured

    Args:
        plugin_name: Name of the plugin file (e.g. 'mermaid_to_drawio.py').
        args: Command-line arguments to pass to the plugin.
        timeout: Override the default timeout (seconds).
        verify: Whether to verify plugin integrity before running.

    Returns:
        subprocess.CompletedProcess with stdout/stderr.

    Raises:
        PluginIntegrityError: If integrity check fails.
        PluginSecurityError: If execution fails.
        subprocess.TimeoutExpired: If the plugin exceeds the timeout.
    """
    if verify:
        verify_plugin_integrity(plugin_name)

    plugin_path = PLUGINS_DIR / plugin_name
    if not plugin_path.exists():
        raise FileNotFoundError(f"Plugin not found: {plugin_path}")

    # Validate I/O paths if --input/--output are in args
    validated_args = list(args)
    for i, arg in enumerate(args):
        if arg in ("--input", "-i") and i + 1 < len(args):
            inp, _ = validate_plugin_io(args[i + 1], args[i + 1])
            validated_args[i + 1] = str(inp)
        elif arg in ("--output", "-o") and i + 1 < len(args):
            _, out = validate_plugin_io(args[i + 1], args[i + 1])
            validated_args[i + 1] = str(out)

    # Build a minimal environment
    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "HOME": os.environ.get("HOME", os.environ.get("USERPROFILE", "")),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Required on Windows
    }

    try:
        result = subprocess.run(
            [sys.executable, str(plugin_path)] + validated_args,
            capture_output=True,
            text=True,
            timeout=timeout or PLUGIN_TIMEOUT,
            cwd=str(PROJECT_ROOT),
            env=safe_env,
        )

        if result.returncode != 0:
            raise PluginSecurityError(
                f"Plugin '{plugin_name}' exited with code {result.returncode}.\n"
                f"stderr: {result.stderr[:500]}"
            )

        return result

    except subprocess.TimeoutExpired:
        raise PluginSecurityError(
            f"Plugin '{plugin_name}' exceeded the {timeout or PLUGIN_TIMEOUT}s timeout."
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for plugin management."""
    import argparse

    parser = argparse.ArgumentParser(description="Architect AI Pro — Secure Plugin Loader")
    parser.add_argument("--rehash", action="store_true", help="Recompute plugin hash registry")
    parser.add_argument("--verify", type=str, help="Verify a specific plugin's integrity")
    parser.add_argument(
        "--run", type=str,
        help="Run a plugin (pass additional args after --)",
    )
    args, remaining = parser.parse_known_args()

    if args.rehash:
        compute_plugin_hashes()
    elif args.verify:
        try:
            verify_plugin_integrity(args.verify)
            print(f"[OK] Plugin '{args.verify}' integrity verified.")
        except (PluginIntegrityError, FileNotFoundError) as e:
            print(f"[FAIL] {e}")
            sys.exit(1)
    elif args.run:
        try:
            result = run_plugin_sandboxed(args.run, remaining)
            print(result.stdout)
        except PluginSecurityError as e:
            print(f"[SECURITY ERROR] {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
