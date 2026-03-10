#!/usr/bin/env python3
"""confmt — config file format converter and validator.

Zero dependencies (uses stdlib tomllib for TOML on Python 3.11+).
Convert between JSON, TOML, and INI. Validate, pretty-print, diff configs.

Usage:
    confmt.py <file> [--to json|toml|ini] [--output out.json]
    confmt.py <file> --validate
    confmt.py <file> --flatten
    confmt.py <file> --get "section.key"
    confmt.py diff <file1> <file2>
"""

import argparse
import configparser
import json
import sys
from io import StringIO
from pathlib import Path

try:
    import tomllib
    HAS_TOML = True
except ImportError:
    try:
        import tomli as tomllib
        HAS_TOML = True
    except ImportError:
        HAS_TOML = False

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def detect_format(path: str) -> str:
    """Detect config format from extension."""
    ext = Path(path).suffix.lower()
    fmt_map = {
        '.json': 'json', '.jsonc': 'json',
        '.toml': 'toml',
        '.ini': 'ini', '.cfg': 'ini', '.conf': 'ini',
        '.env': 'env',
    }
    return fmt_map.get(ext, 'json')


def parse_file(path: str, fmt: str = None) -> dict:
    """Parse a config file into a dict."""
    fmt = fmt or detect_format(path)
    text = Path(path).read_text(encoding='utf-8', errors='replace')

    if fmt == 'json':
        # Strip comments for JSONC support
        lines = []
        for line in text.split('\n'):
            stripped = line.lstrip()
            if not stripped.startswith('//'):
                lines.append(line)
        return json.loads('\n'.join(lines))

    elif fmt == 'toml':
        if not HAS_TOML:
            print(f"{RED}TOML support requires Python 3.11+ or tomli package{RESET}")
            sys.exit(1)
        return tomllib.loads(text)

    elif fmt == 'ini':
        cp = configparser.ConfigParser()
        cp.read_string(text)
        result = {}
        for section in cp.sections():
            result[section] = dict(cp[section])
        if cp.defaults():
            result['DEFAULT'] = dict(cp.defaults())
        return result

    elif fmt == 'env':
        result = {}
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                val = val.strip().strip('"\'')
                result[key.strip()] = val
        return result

    else:
        raise ValueError(f"Unknown format: {fmt}")


def to_json(data: dict) -> str:
    return json.dumps(data, indent=2, default=str)


def to_toml(data: dict, prefix: str = "") -> str:
    """Convert dict to TOML string."""
    lines = []
    simple = {}
    tables = {}

    for k, v in data.items():
        if isinstance(v, dict):
            tables[k] = v
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            tables[k] = v
        else:
            simple[k] = v

    for k, v in simple.items():
        lines.append(f"{k} = {_toml_value(v)}")

    for k, v in tables.items():
        if isinstance(v, list):
            for item in v:
                lines.append(f"\n[[{prefix}{k}]]")
                lines.append(to_toml(item, f"{prefix}{k}."))
        else:
            lines.append(f"\n[{prefix}{k}]")
            lines.append(to_toml(v, f"{prefix}{k}."))

    return '\n'.join(lines)


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, str):
        return json.dumps(v)
    elif isinstance(v, list):
        return "[" + ", ".join(_toml_value(i) for i in v) + "]"
    return json.dumps(str(v))


def to_ini(data: dict) -> str:
    cp = configparser.ConfigParser()
    for section, values in data.items():
        if isinstance(values, dict):
            cp[section] = {k: str(v) for k, v in values.items()}
        else:
            if 'main' not in cp:
                cp['main'] = {}
            cp['main'][section] = str(values)
    output = StringIO()
    cp.write(output)
    return output.getvalue()


def flatten(data: dict, prefix: str = "") -> dict:
    """Flatten nested dict to dot-notation keys."""
    result = {}
    for k, v in data.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            result.update(flatten(v, key))
        else:
            result[key] = v
    return result


def get_value(data: dict, path: str):
    """Get a nested value by dot-notation path."""
    keys = path.split('.')
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    return current


def diff_configs(data1: dict, data2: dict, path1: str, path2: str):
    """Show differences between two configs."""
    flat1 = flatten(data1)
    flat2 = flatten(data2)
    all_keys = sorted(set(flat1) | set(flat2))

    added = removed = changed = same = 0
    for key in all_keys:
        in1 = key in flat1
        in2 = key in flat2
        if in1 and not in2:
            print(f"  {RED}- {key} = {flat1[key]}{RESET}")
            removed += 1
        elif in2 and not in1:
            print(f"  {GREEN}+ {key} = {flat2[key]}{RESET}")
            added += 1
        elif flat1[key] != flat2[key]:
            print(f"  {YELLOW}~ {key}: {flat1[key]} → {flat2[key]}{RESET}")
            changed += 1
        else:
            same += 1

    print(f"\n📊 {same} same, {GREEN}+{added}{RESET} added, {RED}-{removed}{RESET} removed, {YELLOW}~{changed}{RESET} changed")


def main():
    parser = argparse.ArgumentParser(description="confmt — config format converter")
    parser.add_argument("file", help="Config file")
    parser.add_argument("file2", nargs='?', help="Second file (for --diff)")
    parser.add_argument("--to", choices=["json", "toml", "ini"], help="Output format")
    parser.add_argument("--from", dest="from_fmt", choices=["json", "toml", "ini", "env"])
    parser.add_argument("--output", "-o", help="Output file")
    parser.add_argument("--validate", action="store_true", help="Validate only")
    parser.add_argument("--flatten", action="store_true", help="Flatten to dot notation")
    parser.add_argument("--get", help="Get value by dot path")
    parser.add_argument("--diff", action="store_true", help="Diff two config files")
    parser.add_argument("--no-color", action="store_true")

    args = parser.parse_args()

    if args.no_color:
        global RED, GREEN, YELLOW, CYAN, BOLD, DIM, RESET
        RED = GREEN = YELLOW = CYAN = BOLD = DIM = RESET = ""

    if args.diff:
        if not args.file2:
            print(f"{RED}--diff requires two files{RESET}")
            sys.exit(1)
        data1 = parse_file(args.file)
        data2 = parse_file(args.file2)
        print(f"📋 Diff: {args.file} vs {args.file2}\n")
        diff_configs(data1, data2, args.file, args.file2)
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    try:
        data = parse_file(args.file, args.from_fmt)
    except Exception as e:
        print(f"{RED}✗ Parse error: {e}{RESET}")
        sys.exit(1)

    if args.validate:
        print(f"{GREEN}✓ Valid {detect_format(args.file).upper()} ({len(flatten(data))} keys){RESET}")
        return

    if args.get:
        val = get_value(data, args.get)
        if val is None:
            print(f"{RED}Key not found: {args.get}{RESET}")
            sys.exit(1)
        if isinstance(val, (dict, list)):
            print(json.dumps(val, indent=2))
        else:
            print(val)
        return

    if args.flatten:
        flat = flatten(data)
        for k, v in sorted(flat.items()):
            print(f"  {CYAN}{k}{RESET} = {v}")
        return

    # Convert
    out_fmt = args.to or 'json'
    converters = {'json': to_json, 'toml': to_toml, 'ini': to_ini}
    output = converters[out_fmt](data)

    if args.output:
        Path(args.output).write_text(output)
        print(f"✓ Written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
