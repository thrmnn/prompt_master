"""Section-scoped variation generation.

Generates prompt variations for a *single* section of a structured
prompt, rather than regenerating the entire prompt.  This enables
the TUI's inline variation drawer to offer quick alternatives
without an expensive full-prompt round-trip.
"""

from __future__ import annotations

import random
from typing import List, Optional

from prompt_master.fallback import fallback_optimize
from prompt_master.vibe import (
    DIMENSIONS,
    Variation,
    _apply_dimension,
    _parse_sections,
    _render_sections,
    parse_variations,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_section_variations(
    section_name: str,
    section_content: str,
    target: str = "general",
    count: int = 3,
    dimensions: Optional[List[str]] = None,
    client=None,
) -> List[dict]:
    """Generate variations for a single section of a prompt.

    Parameters
    ----------
    section_name:
        The markdown heading of the section (e.g. ``"Role"``).
    section_content:
        The current text content of that section.
    target:
        Domain target (``"general"``, ``"code"``, etc.).
    count:
        Number of variations to produce.
    dimensions:
        Which vibe dimensions to explore.  ``None`` means auto-select
        a diverse set.
    client:
        An optional :class:`~prompt_master.client.ClaudeClient`.  When
        provided the function attempts an API call; otherwise it falls
        back to the template-based approach.

    Returns
    -------
    list[dict]
        Each dict has keys ``dimension``, ``value``, and ``content``
        where *content* is the rewritten section text (not the full
        prompt).
    """
    if client is not None:
        try:
            return _api_section_variations(
                section_name,
                section_content,
                target,
                count,
                dimensions,
                client,
            )
        except Exception:
            # Fall through to template-based generation on any API error.
            pass

    return _fallback_section_variations(
        section_name,
        section_content,
        target,
        count,
        dimensions,
    )


# ---------------------------------------------------------------------------
# API-based generation
# ---------------------------------------------------------------------------

def _api_section_variations(
    section_name: str,
    section_content: str,
    target: str,
    count: int,
    dimensions: Optional[List[str]],
    client,
) -> List[dict]:
    """Generate section variations via the Claude API.

    Constructs a focused prompt asking the model to rewrite *only* the
    given section along the requested dimensions, then parses the
    structured ``===VARIATION_START===`` / ``===VARIATION_END===``
    markers from the response.
    """
    from prompt_master.prompts import build_vibe_system_prompt

    dim_instruction = ""
    if dimensions:
        dim_instruction = f"Focus on these dimensions: {', '.join(dimensions)}."
    else:
        dim_instruction = (
            "Choose diverse dimensions to create meaningfully "
            "different alternatives."
        )

    user_message = (
        f"I have a prompt section called **{section_name}** with this content:\n\n"
        f"```\n{section_content}\n```\n\n"
        f"Generate exactly {count} alternative versions of *only* this section.\n"
        f"{dim_instruction}\n\n"
        f"Each variation must be a complete replacement for the section content "
        f"(not the full prompt). Output each using the standard variation markers."
    )

    system = build_vibe_system_prompt(target)
    response = client.generate(system, user_message, max_tokens=2048)
    parsed: List[Variation] = parse_variations(response)

    results: List[dict] = []
    for v in parsed[:count]:
        results.append({
            "dimension": v.dimension,
            "value": v.value,
            "content": v.prompt,
        })
    return results


# ---------------------------------------------------------------------------
# Template / fallback generation
# ---------------------------------------------------------------------------

def _fallback_section_variations(
    section_name: str,
    section_content: str,
    target: str,
    count: int,
    dimensions: Optional[List[str]] = None,
) -> List[dict]:
    """Generate section variations using template-based dimension application.

    Strategy:
    1.  Wrap the section content in a minimal single-section prompt.
    2.  Apply :func:`~prompt_master.vibe._apply_dimension` which rewrites
        known sections (Role, Output Format, Task, etc.) in place.
    3.  Extract the modified section content back out.
    4.  Repeat across different dimension/value pairs to produce diverse
        alternatives.
    """
    # Choose which dimensions and values to explore.
    chosen_dims = _select_dimensions(count, dimensions)

    results: List[dict] = []
    for dim, value in chosen_dims:
        # Build a minimal prompt with only this section so that
        # _apply_dimension can operate on it.
        mini_prompt = f"# {section_name}\n{section_content}"
        modified_prompt = _apply_dimension(mini_prompt, dim, value)

        # Parse sections back out.
        sections = _parse_sections(modified_prompt)

        # The section we care about may have been renamed or a new
        # section may have been added by the dimension transform.
        # Prefer the original name; fall back to the first non-preamble.
        new_content = sections.get(section_name)
        if new_content is None:
            # Pick the first non-preamble section.
            for header, body in sections.items():
                if header != "_preamble" and body:
                    new_content = body
                    break

        # If the transform produced nothing useful, skip.
        if not new_content or new_content.strip() == section_content.strip():
            # Generate a simple annotated variant instead.
            new_content = (
                f"[{dim}={value}] {section_content}"
            )

        results.append({
            "dimension": dim,
            "value": value,
            "content": new_content.strip(),
        })

        if len(results) >= count:
            break

    return results[:count]


def _select_dimensions(
    count: int,
    dimensions: Optional[List[str]] = None,
) -> List[tuple[str, str]]:
    """Pick *count* (dimension, value) pairs for variation generation.

    If *dimensions* is provided, cycle through them; otherwise pick
    a diverse random sample from all available dimensions.
    """
    pairs: List[tuple[str, str]] = []

    if dimensions:
        # Cycle through the requested dimensions.
        for i in range(count):
            dim = dimensions[i % len(dimensions)]
            values = DIMENSIONS.get(dim, ["default"])
            value = values[i % len(values)]
            pairs.append((dim, value))
    else:
        # Sample across all dimensions for maximum diversity.
        all_pairs: List[tuple[str, str]] = []
        for dim, values in DIMENSIONS.items():
            for val in values:
                all_pairs.append((dim, val))
        # Shuffle and pick, ensuring dimension diversity where possible.
        random.shuffle(all_pairs)
        seen_dims: set[str] = set()
        # First pass: one per dimension.
        for pair in all_pairs:
            if pair[0] not in seen_dims:
                pairs.append(pair)
                seen_dims.add(pair[0])
            if len(pairs) >= count:
                break
        # Second pass: fill remaining from the shuffled pool.
        if len(pairs) < count:
            for pair in all_pairs:
                if pair not in pairs:
                    pairs.append(pair)
                if len(pairs) >= count:
                    break

    return pairs[:count]
