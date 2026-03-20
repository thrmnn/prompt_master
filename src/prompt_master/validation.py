"""Input validation and template schema validation."""

from __future__ import annotations

from typing import Dict, List

import click


class ValidationError(Exception):
    pass


def validate_idea(idea: str) -> str:
    """Validate and clean user idea input. Raises ValidationError if invalid."""
    if not idea or not idea.strip():
        raise ValidationError("Idea cannot be empty.")
    idea = idea.strip()
    if len(idea) < 3:
        raise ValidationError("Idea is too short — please provide at least a few words.")
    if len(idea) > 10000:
        raise ValidationError("Idea is too long (max 10,000 characters).")
    return idea


# Required and optional fields for template schema validation
TEMPLATE_SCHEMA = {
    "required_sections": ["meta"],
    "meta_required": ["name"],
    "optional_sections": ["role", "structure", "defaults", "example"],
}


def validate_template(data: Dict, name: str = "unknown") -> List[str]:
    """Validate a template dict against the expected schema.

    Returns a list of warning strings. Raises ValidationError for critical issues.
    """
    warnings: list[str] = []

    if not isinstance(data, dict):
        raise ValidationError(f"Template '{name}' is not a valid TOML document.")

    # Check meta section
    meta = data.get("meta")
    if not meta:
        warnings.append(f"Template '{name}' is missing [meta] section.")
    elif not isinstance(meta, dict):
        raise ValidationError(f"Template '{name}': [meta] must be a table.")
    else:
        if "name" not in meta:
            warnings.append(f"Template '{name}': [meta] missing 'name' field.")
        if "description" not in meta:
            warnings.append(f"Template '{name}': [meta] missing 'description' field.")

    # Check role section
    role = data.get("role")
    if role and not isinstance(role, dict):
        raise ValidationError(f"Template '{name}': [role] must be a table.")
    if role and "default" not in role:
        warnings.append(f"Template '{name}': [role] has no 'default' field.")

    # Check defaults section
    defaults = data.get("defaults")
    if defaults and not isinstance(defaults, dict):
        raise ValidationError(f"Template '{name}': [defaults] must be a table.")

    return warnings
