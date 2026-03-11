#!/usr/bin/env python3
"""Go code guardrail validation for deep-implement.

Validates Go source files against hexagonal architecture constraints:
file sizes, function lengths, import direction, and prohibited patterns.

Ported from devx-design-crew/impl_guardrails.py — simplified for
deep-implement (no exception system, no LLM fallback).

Usage:
    uv run scripts/checks/validate_go_guardrails.py --target-dir /path/to/repo
    uv run scripts/checks/validate_go_guardrails.py --target-dir /path/to/repo --override max_file_lines=450
"""

import argparse
import json
import os
import re
import subprocess
import sys

# --- Constants (from CLAUDE.md file sizing table) ---

MAX_FILE_LINES = 300        # service/adapter files
MAX_FUNCTION_LINES = 75     # non-test functions
MAX_PORT_LINES = 100        # port interface files
MAX_ENTITY_LINES = 250      # domain entity files
MAX_HANDLER_LINES = 250     # handler files
MAX_TEST_FILE_LINES = 500   # test files
MAX_TEST_FUNCTION_LINES = 150  # test functions

# Regex for Go function definitions
_FUNC_RE = re.compile(r"^func\s", re.MULTILINE)

# Regex for Go import blocks
_IMPORT_SINGLE_RE = re.compile(r'^import\s+"([^"]+)"', re.MULTILINE)
_IMPORT_BLOCK_RE = re.compile(r"^import\s*\((.*?)\)", re.MULTILINE | re.DOTALL)
_IMPORT_LINE_RE = re.compile(r'"([^"]+)"')

# Regex for package declaration
_PACKAGE_RE = re.compile(r"^package\s+\w+", re.MULTILINE)

# Prohibited patterns: (regex, message, skip_condition)
# skip_condition: "main" = skip in /cmd/ paths, "test" = skip in _test.go
_PROHIBITED_PATTERNS = [
    (re.compile(r'(?:password|secret|api[_-]?key)\s*[:=]\s*"[^"]{8,}"'), "Hardcoded secret detected", None),
    (re.compile(r"\bos\.Exit\b"), "os.Exit() in non-main package", "cmd"),
    (re.compile(r"\bpanic\b\s*\("), "panic() call (use error returns instead)", "test"),
]

# Hex architecture layers — inner must not import outer
_HEX_LAYERS = {
    "domain": 0,
    "ports": 1,
    "service": 2,
    "handler": 3,
    "adapter": 4,
}


# --- File discovery ---

def discover_go_files(target_dir: str) -> list[str]:
    """Find Go files to validate using git or filesystem walk."""
    go_files = []

    # Try git diff HEAD first (changed files)
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=target_dir, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            for f in result.stdout.strip().splitlines():
                if f.endswith(".go"):
                    full = os.path.join(target_dir, f)
                    if os.path.isfile(full):
                        go_files.append(f)
            if go_files:
                return go_files
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Try git ls-files (all tracked files)
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.go"],
            capture_output=True, text=True, cwd=target_dir, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            for f in result.stdout.strip().splitlines():
                full = os.path.join(target_dir, f)
                if os.path.isfile(full):
                    go_files.append(f)
            if go_files:
                return go_files
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback: walk filesystem
    for root, _dirs, files in os.walk(target_dir):
        for fname in files:
            if fname.endswith(".go"):
                rel = os.path.relpath(os.path.join(root, fname), target_dir)
                go_files.append(rel)

    return go_files


# --- Validation functions ---

def max_lines_for_file(filepath: str) -> int:
    """Determine max lines based on file type/location."""
    if filepath.endswith("_test.go"):
        return MAX_TEST_FILE_LINES
    if "/ports/" in filepath:
        return MAX_PORT_LINES
    if "/domain/" in filepath:
        return MAX_ENTITY_LINES
    if "/handler/" in filepath:
        return MAX_HANDLER_LINES
    return MAX_FILE_LINES


def check_file_size(filepath: str, content: str) -> list[str]:
    """Check file does not exceed line limit for its hex layer."""
    line_count = len(content.split("\n"))
    max_lines = max_lines_for_file(filepath)
    if line_count > max_lines:
        return [f"{filepath}: {line_count} lines (max {max_lines})"]
    return []


def check_function_lengths(filepath: str, content: str) -> list[str]:
    """Check no function exceeds length limit."""
    violations = []
    lines = content.split("\n")
    func_starts: list[tuple[int, str]] = []

    for i, line in enumerate(lines):
        if _FUNC_RE.match(line):
            rest = line[len("func "):].strip()
            if rest.startswith("("):
                # Method receiver: func (r *Repo) Name(
                close = rest.index(")")
                rest = rest[close + 1:].strip()
            name = rest.split("(")[0].strip()
            func_starts.append((i, name))

    is_test = filepath.endswith("_test.go")
    max_func = MAX_TEST_FUNCTION_LINES if is_test else MAX_FUNCTION_LINES

    for idx, (start, name) in enumerate(func_starts):
        end = func_starts[idx + 1][0] if idx + 1 < len(func_starts) else len(lines)
        func_len = end - start
        if func_len > max_func:
            violations.append(
                f"{filepath}:{start + 1} func {name}: {func_len} lines (max {max_func})"
            )

    return violations


def check_package_declaration(filepath: str, content: str) -> list[str]:
    """Check file has a package declaration."""
    if not _PACKAGE_RE.search(content):
        return [f"{filepath}: missing package declaration"]
    return []


def extract_imports(content: str) -> list[str]:
    """Extract all import paths from Go source."""
    imports = []
    for m in _IMPORT_SINGLE_RE.finditer(content):
        imports.append(m.group(1))
    for m in _IMPORT_BLOCK_RE.finditer(content):
        block = m.group(1)
        for line_m in _IMPORT_LINE_RE.finditer(block):
            imports.append(line_m.group(1))
    return imports


def get_hex_layer(filepath: str) -> tuple[str, int] | None:
    """Return (layer_name, level) if file is in a hex layer, else None."""
    for layer_name, level in _HEX_LAYERS.items():
        if f"/internal/{layer_name}/" in filepath or filepath.endswith(f"/internal/{layer_name}"):
            return layer_name, level
    return None


def check_hex_layers(filepath: str, content: str) -> list[str]:
    """Check hex architecture import direction (inner must not import outer)."""
    violations = []
    layer_info = get_hex_layer(filepath)
    if not layer_info:
        return violations

    file_layer, file_level = layer_info
    imports = extract_imports(content)

    for imp in imports:
        for layer_name, level in _HEX_LAYERS.items():
            if f"/internal/{layer_name}" in imp and level > file_level:
                violations.append(
                    f"{filepath}: {file_layer} layer imports {layer_name} layer ({imp})"
                )

    return violations


def check_cross_service_imports(filepath: str, content: str) -> list[str]:
    """Check for imports of other services' internal packages."""
    violations = []
    imports = extract_imports(content)

    for imp in imports:
        if "/internal/" in imp and "services/" in imp:
            # Extract service name from file path
            file_service = None
            if "services/" in filepath:
                parts = filepath.split("services/")[1].split("/")
                if parts:
                    file_service = parts[0]

            # Extract service name from import
            imp_service = None
            if "services/" in imp:
                parts = imp.split("services/")[1].split("/")
                if parts:
                    imp_service = parts[0]

            if file_service and imp_service and file_service != imp_service:
                violations.append(
                    f"{filepath}: imports internal package from service '{imp_service}': {imp}"
                )

    return violations


def check_self_imports(filepath: str, content: str) -> list[str]:
    """Check for self-import (import cycle)."""
    violations = []
    imports = extract_imports(content)

    # Get file's directory path components
    file_dir = "/".join(filepath.split("/")[:-1])
    if not file_dir:
        return violations

    for imp in imports:
        if file_dir and imp.endswith("/" + file_dir.split("/")[-1]):
            # Check the full path matches
            if file_dir in imp:
                violations.append(
                    f"{filepath}: self-import detected ({imp})"
                )

    return violations


def check_prohibited_patterns(filepath: str, content: str) -> list[str]:
    """Check for prohibited patterns (secrets, os.Exit, panic)."""
    violations = []
    is_test = filepath.endswith("_test.go")
    is_cmd = "/cmd/" in filepath or filepath.startswith("cmd/")

    for pattern, message, skip in _PROHIBITED_PATTERNS:
        if pattern.search(content):
            if skip == "cmd" and is_cmd:
                continue
            if skip == "test" and is_test:
                continue
            violations.append(f"{filepath}: {message}")

    return violations


def validate_file(filepath: str, content: str) -> list[str]:
    """Run all validation checks on a single file."""
    violations = []
    violations.extend(check_file_size(filepath, content))
    violations.extend(check_function_lengths(filepath, content))
    violations.extend(check_package_declaration(filepath, content))
    violations.extend(check_hex_layers(filepath, content))
    violations.extend(check_cross_service_imports(filepath, content))
    violations.extend(check_self_imports(filepath, content))
    violations.extend(check_prohibited_patterns(filepath, content))
    return violations


def validate_directory(target_dir: str) -> dict:
    """Validate all Go files in target directory."""
    go_files = discover_go_files(target_dir)
    all_violations = []
    files_checked = 0

    for relpath in go_files:
        full_path = os.path.join(target_dir, relpath)
        try:
            with open(full_path, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        files_checked += 1
        violations = validate_file(relpath, content)
        all_violations.extend(violations)

    passed = len(all_violations) == 0
    summary = (
        f"{len(all_violations)} violation{'s' if len(all_violations) != 1 else ''} "
        f"in {files_checked} Go file{'s' if files_checked != 1 else ''}"
    )

    return {
        "passed": passed,
        "files_checked": files_checked,
        "violations": all_violations,
        "summary": summary,
    }


def apply_overrides(overrides: dict[str, str]) -> None:
    """Apply CLI --override values to module constants."""
    mapping = {
        "max_file_lines": "MAX_FILE_LINES",
        "max_function_lines": "MAX_FUNCTION_LINES",
        "max_port_lines": "MAX_PORT_LINES",
        "max_entity_lines": "MAX_ENTITY_LINES",
        "max_handler_lines": "MAX_HANDLER_LINES",
        "max_test_file_lines": "MAX_TEST_FILE_LINES",
        "max_test_function_lines": "MAX_TEST_FUNCTION_LINES",
    }
    for key, value in overrides.items():
        const_name = mapping.get(key)
        if const_name:
            globals()[const_name] = int(value)
        else:
            print(f"Warning: unknown override key '{key}'", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Go code guardrails")
    parser.add_argument("--target-dir", required=True, help="Path to Go repository")
    parser.add_argument(
        "--override", action="append", default=[],
        help="Override a limit: key=value (e.g., max_file_lines=450)",
    )
    args = parser.parse_args()

    # Parse overrides
    overrides = {}
    for item in args.override:
        if "=" in item:
            k, v = item.split("=", 1)
            overrides[k.strip()] = v.strip()

    if overrides:
        apply_overrides(overrides)

    result = validate_directory(args.target_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
