# confmt

Config file format converter and inspector. Zero dependencies.

## Usage

```bash
# Pretty-print as JSON
python3 confmt.py config.toml --to json

# Convert TOML to JSON
python3 confmt.py config.toml --to json -o config.json

# Validate
python3 confmt.py config.json --validate

# Flatten to dot notation
python3 confmt.py config.json --flatten

# Get a specific value
python3 confmt.py config.json --get "database.host"

# Diff two configs
python3 confmt.py old.json new.json --diff

# Parse .env files
python3 confmt.py .env --to json
```

## Supported Formats

- **JSON** / JSONC (with `//` comments)
- **TOML** (Python 3.11+ or tomli)
- **INI** / .cfg / .conf
- **.env** files

## Philosophy

One file. Zero deps. Does one thing well.
