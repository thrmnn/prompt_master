"""Template loading, saving, and discovery."""

import shutil
from pathlib import Path
from typing import Dict, List

try:
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

BUILTIN_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
USER_TEMPLATE_DIR = Path.home() / ".prompt_master" / "templates"


class TemplateNotFoundError(Exception):
    pass


def load_template(name_or_path: str, validate: bool = True) -> Dict:
    """Load a template by name (user > builtin) or by file path."""
    from prompt_master.validation import validate_template

    path = Path(name_or_path)
    if path.exists() and path.suffix == ".toml":
        data = _parse(path)
        if validate:
            validate_template(data, name=path.stem)
        return data

    for directory in [USER_TEMPLATE_DIR, BUILTIN_TEMPLATE_DIR]:
        candidate = directory / f"{name_or_path}.toml"
        if candidate.exists():
            data = _parse(candidate)
            if validate:
                validate_template(data, name=name_or_path)
            return data

    raise TemplateNotFoundError(f"Template '{name_or_path}' not found")


def _parse(path: Path) -> Dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def list_templates() -> List[Dict]:
    """Return metadata for all available templates (builtin + user)."""
    seen = set()
    results = []

    for directory in [USER_TEMPLATE_DIR, BUILTIN_TEMPLATE_DIR]:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.toml")):
            name = path.stem
            if name in seen:
                continue
            seen.add(name)
            try:
                data = _parse(path)
                meta = data.get("meta", {})
                results.append(
                    {
                        "name": name,
                        "description": meta.get("description", ""),
                        "source": "user" if directory == USER_TEMPLATE_DIR else "builtin",
                        "path": str(path),
                    }
                )
            except Exception:
                continue

    return results


def show_template(name: str) -> str:
    """Return the raw text content of a template."""
    for directory in [USER_TEMPLATE_DIR, BUILTIN_TEMPLATE_DIR]:
        candidate = directory / f"{name}.toml"
        if candidate.exists():
            return candidate.read_text()

    raise TemplateNotFoundError(f"Template '{name}' not found")


def save_template(name: str, source_path: str) -> Path:
    """Copy a template file to the user template directory."""
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source file '{source_path}' not found")

    # Validate it's valid TOML
    _parse(src)

    USER_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    dest = USER_TEMPLATE_DIR / f"{name}.toml"
    shutil.copy2(src, dest)
    return dest
