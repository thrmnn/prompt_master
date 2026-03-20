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
    1.  Build a FULL prompt via fallback_optimize (so all sections exist).
    2.  Replace the target section with our content.
    3.  Apply _apply_dimension to the full prompt (transforms work properly).
    4.  Extract just our target section back out.
    """
    chosen_dims = _select_dimensions(count, dimensions, section_name=section_name)

    # Build a full prompt so _apply_dimension has all sections to work with
    base_prompt = fallback_optimize(section_content, target)
    base_sections = _parse_sections(base_prompt)
    # Inject our actual section content
    base_sections[section_name] = section_content

    results: List[dict] = []
    for dim, value in chosen_dims:
        full_prompt = _render_sections(base_sections)
        modified_prompt = _apply_dimension(full_prompt, dim, value)
        modified_sections = _parse_sections(modified_prompt)

        # Extract the section we care about
        new_content = modified_sections.get(section_name, "")

        # Also check if a "Style Constraint" was added — merge it in
        # for sections where the dimension didn't directly transform ours
        style = modified_sections.get("Style Constraint", "")

        if new_content and new_content.strip() != section_content.strip():
            # The dimension actually changed our section — use it
            final_content = new_content.strip()
        elif style:
            # The dimension added a style constraint — prepend it
            final_content = f"{style.strip()}\n\n{section_content}"
        else:
            # Nothing changed — build a meaningful rewrite by hand
            final_content = _manual_section_variant(section_name, section_content, dim, value)

        results.append({
            "dimension": dim,
            "value": value,
            "content": final_content,
        })

        if len(results) >= count:
            break

    return results[:count]


def _manual_section_variant(section_name: str, content: str, dim: str, value: str) -> str:
    """Generate a meaningful variant when _apply_dimension didn't change our section."""
    # Universal rewrites that work for any section content
    rewrites = {
        # Tone
        ("tone", "formal"): lambda c: f"In a formal, professional manner:\n{c}",
        ("tone", "casual"): lambda c: f"In a relaxed, approachable way:\n{c}",
        ("tone", "technical"): lambda c: f"Using precise technical terminology:\n{c}\n\nInclude specifications and standards where applicable.",
        ("tone", "playful"): lambda c: f"In an engaging, fun way:\n{c}\n\nUse creative analogies to make concepts memorable.",
        ("tone", "authoritative"): lambda c: f"With authority and confidence:\n{c}\n\nBe definitive. Recommend best practices, not options.",
        ("tone", "empathetic"): lambda c: f"With empathy and patience:\n{c}\n\nAcknowledge challenges. Guide step by step.",
        # Audience
        ("audience", "beginner"): lambda c: f"For someone with no prior experience:\n{c}\n\nDefine all terms. Use simple analogies. Build from first principles.",
        ("audience", "expert"): lambda c: f"For a domain expert (skip basics):\n{c}\n\nFocus on edge cases, trade-offs, and advanced patterns.",
        ("audience", "executive"): lambda c: f"For a decision-maker (lead with impact):\n{c}\n\nQuantify benefits. Keep it concise. End with clear recommendations.",
        ("audience", "child"): lambda c: f"For a curious 10-year-old:\n{c}\n\nUse fun comparisons and real-world examples. Keep sentences short.",
        ("audience", "developer"): lambda c: f"For an experienced developer:\n{c}\n\nInclude code snippets, API references, and practical implementation details.",
        ("audience", "general"): lambda c: f"For a general audience:\n{c}\n\nDefine key terms on first use. Balance accessibility with depth.",
        # Format
        ("format", "prose"): lambda c: f"In flowing prose (no bullet points):\n{c}",
        ("format", "bullets"): lambda c: "As bullet points:\n" + "\n".join(f"- {line.strip()}" for line in c.splitlines() if line.strip()),
        ("format", "step-by-step"): lambda c: "As a numbered step-by-step guide:\n" + "\n".join(f"{i+1}. {line.strip()}" for i, line in enumerate(c.splitlines()) if line.strip()),
        ("format", "code"): lambda c: f"{c}\n\nInclude working code examples for every concept. Use fenced code blocks.",
        ("format", "dialogue"): lambda c: f"Framed as a Q&A dialogue:\nQ: What does this involve?\nA: {c}",
        ("format", "report"): lambda c: f"Structured as a formal report:\n\n## Overview\n{c}\n\n## Details\n[expand on each aspect]",
        # Specificity
        ("specificity", "broad"): lambda c: f"Explore the full breadth of:\n{c}\n\nCover multiple approaches, angles, and trade-offs.",
        ("specificity", "narrow"): lambda c: f"Focus deeply on the single most critical aspect of:\n{c}\n\nIgnore tangential concerns. Go deep on this one thing.",
        ("specificity", "exploratory"): lambda c: f"Take an exploratory approach:\n{c}\n\nRaise open questions. Identify unknowns. Map what needs investigation.",
        ("specificity", "precise"): lambda c: f"Be maximally precise:\n{c}\n\nEvery claim must be specific and verifiable. No hedging language.",
        # Style
        ("style", "concise"): lambda c: " ".join(c.split()[:25]) + ("." if len(c.split()) > 25 else ""),
        ("style", "verbose"): lambda c: f"{c}\n\nProvide thorough explanations for every point. Include multiple examples. Anticipate and address follow-up questions.",
        ("style", "academic"): lambda c: f"In academic style:\n{c}\n\nReference established frameworks. Structure as thesis, evidence, conclusion.",
        ("style", "conversational"): lambda c: f"Think of it this way:\n{c}\n\nExplain the 'why' behind each point. Use 'you' and 'we'.",
        ("style", "poetic"): lambda c: f"With vivid, evocative language:\n{c}\n\nUse metaphors and imagery to illuminate the concepts.",
    }

    rewriter = rewrites.get((dim, value))
    if rewriter:
        return rewriter(content)
    # Absolute fallback — should rarely hit this
    return f"[Variation: {dim}={value}]\n{content}"


# Dimensions that directly transform specific sections via _apply_dimension
_SECTION_AFFINITY = {
    "Role": ["tone", "style", "audience"],
    "Task": ["specificity"],
    "Output Format": ["format"],
    "Requirements": ["style"],
    "Context": ["audience"],
}


def _select_dimensions(
    count: int,
    dimensions: Optional[List[str]] = None,
    section_name: Optional[str] = None,
) -> List[tuple[str, str]]:
    """Pick *count* (dimension, value) pairs for variation generation.

    If *dimensions* is provided, cycle through them. Otherwise pick
    a diverse set, prioritizing dimensions with affinity for the section.
    """
    pairs: List[tuple[str, str]] = []

    if dimensions:
        for i in range(count):
            dim = dimensions[i % len(dimensions)]
            values = DIMENSIONS.get(dim, ["default"])
            value = values[i % len(values)]
            pairs.append((dim, value))
    else:
        # Prioritize dimensions that have affinity with this section
        affinity_dims = _SECTION_AFFINITY.get(section_name or "", [])
        all_dims = list(DIMENSIONS.keys())

        # Order: affinity dims first, then the rest
        ordered_dims = affinity_dims + [d for d in all_dims if d not in affinity_dims]

        for dim in ordered_dims:
            if len(pairs) >= count:
                break
            values = DIMENSIONS.get(dim, ["default"])
            # Pick a random interesting value (not the first/most boring one)
            value = random.choice(values)
            pairs.append((dim, value))

        # If we still need more, cycle through with different values
        while len(pairs) < count:
            dim = random.choice(all_dims)
            values = DIMENSIONS.get(dim, ["default"])
            value = random.choice(values)
            if (dim, value) not in pairs:
                pairs.append((dim, value))

    return pairs[:count]
