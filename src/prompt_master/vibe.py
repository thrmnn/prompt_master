"""Vibe Mode — explore prompt variations along dimensions.

Generates multiple prompt variations from a single idea by varying
tone, audience, format, specificity, and style. Supports interactive
tree exploration: pick a variation, mutate it, branch further.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from prompt_master.client import ClaudeClient, NoAPIKeyError
from prompt_master.fallback import fallback_optimize
from prompt_master.prompts import build_vibe_system_prompt

# ── Dimensions ──────────────────────────────────────────────────────────────

DIMENSIONS = {
    "tone": ["formal", "casual", "technical", "playful", "authoritative", "empathetic"],
    "audience": ["beginner", "expert", "executive", "child", "developer", "general"],
    "format": ["prose", "bullets", "step-by-step", "code", "dialogue", "report"],
    "specificity": ["broad", "narrow", "exploratory", "precise"],
    "style": ["concise", "verbose", "academic", "conversational", "poetic"],
}

# ── Variation parsing ───────────────────────────────────────────────────────

VARIATION_START = "===VARIATION_START==="
VARIATION_END = "===VARIATION_END==="

_VARIATION_RE = re.compile(
    r"===VARIATION_START===\s*\n"
    r"dimension:\s*(?P<dimension>[^\n]+)\n"
    r"value:\s*(?P<value>[^\n]+)\n"
    r"---\s*\n"
    r"(?P<prompt>.*?)"
    r"===VARIATION_END===",
    re.DOTALL,
)


@dataclass
class Variation:
    """A single prompt variation."""

    dimension: str
    value: str
    prompt: str
    parent_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "value": self.value,
            "prompt": self.prompt,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Variation":
        return cls(
            dimension=data["dimension"],
            value=data["value"],
            prompt=data["prompt"],
            parent_id=data.get("parent_id"),
        )


def parse_variations(text: str) -> List[Variation]:
    """Parse variation markers from API response text."""
    variations = []
    for match in _VARIATION_RE.finditer(text):
        variations.append(
            Variation(
                dimension=match.group("dimension").strip(),
                value=match.group("value").strip(),
                prompt=match.group("prompt").strip(),
            )
        )
    return variations


# ── Vibe Engine ─────────────────────────────────────────────────────────────


@dataclass
class VibeEngine:
    """Manages prompt variation generation and exploration."""

    idea: str
    target: str = "general"
    variations: List[Variation] = field(default_factory=list)
    _client: Optional[ClaudeClient] = field(default=None, repr=False)

    def _get_client(self) -> ClaudeClient:
        if self._client is None:
            self._client = ClaudeClient()
        return self._client

    def generate_variations(
        self,
        count: int = 4,
        dimensions: Optional[List[str]] = None,
    ) -> List[Variation]:
        """Generate initial variations from the base idea.

        Args:
            count: Number of variations to generate.
            dimensions: Which dimensions to vary. If None, auto-select diverse set.
        """
        dim_instruction = ""
        if dimensions:
            dim_instruction = f"Focus on these dimensions: {', '.join(dimensions)}."
        else:
            dim_instruction = (
                "Choose diverse dimensions to create meaningfully different variations."
            )

        user_message = (
            f"**Base idea:** {self.idea}\n\n"
            f"Generate exactly {count} prompt variations.\n"
            f"{dim_instruction}\n\n"
            f"Each variation must be a complete, self-contained, optimized prompt."
        )

        try:
            client = self._get_client()
            system = build_vibe_system_prompt(self.target)
            response = client.generate(system, user_message, max_tokens=4096)
            new_variations = parse_variations(response)
        except NoAPIKeyError:
            # Fallback: generate structural variations offline
            new_variations = self._fallback_variations(count, dimensions)

        self.variations.extend(new_variations)
        return new_variations

    def mutate(
        self,
        variation_index: int,
        dimension: str,
        value: str,
    ) -> Variation:
        """Mutate an existing variation along a specific dimension.

        Args:
            variation_index: Index of the variation to mutate.
            dimension: Which dimension to change.
            value: New value for that dimension.
        """
        if variation_index >= len(self.variations):
            raise IndexError(f"No variation at index {variation_index}")

        base = self.variations[variation_index]

        user_message = (
            f"**Base prompt to mutate:**\n\n{base.prompt}\n\n"
            f"**Mutation:** Change the {dimension} to: {value}\n\n"
            f"Output exactly 1 variation with the mutation applied. "
            f"Keep everything else the same but adapt the prompt to fit "
            f"the new {dimension}."
        )

        try:
            client = self._get_client()
            system = build_vibe_system_prompt(self.target)
            response = client.generate(system, user_message, max_tokens=2048)
            parsed = parse_variations(response)
            if parsed:
                mutation = parsed[0]
                mutation.parent_id = variation_index
                self.variations.append(mutation)
                return mutation
        except NoAPIKeyError:
            pass

        # Fallback: create a simple mutation
        mutation = Variation(
            dimension=dimension,
            value=value,
            prompt=f"[Mutated: {dimension}={value}]\n\n{base.prompt}",
            parent_id=variation_index,
        )
        self.variations.append(mutation)
        return mutation

    def compare(self, indices: Optional[List[int]] = None) -> List[dict]:
        """Return comparison data for selected variations (or all).

        Returns list of dicts with index, dimension, value, prompt preview, length.
        """
        if indices is None:
            indices = list(range(len(self.variations)))

        results = []
        for i in indices:
            if i < len(self.variations):
                v = self.variations[i]
                results.append(
                    {
                        "index": i,
                        "dimension": v.dimension,
                        "value": v.value,
                        "preview": v.prompt[:100] + ("..." if len(v.prompt) > 100 else ""),
                        "length": len(v.prompt),
                        "parent_id": v.parent_id,
                    }
                )
        return results

    def _fallback_variations(
        self, count: int, dimensions: Optional[List[str]] = None
    ) -> List[Variation]:
        """Generate variations using template-based approach (no API)."""
        dims = dimensions or list(DIMENSIONS.keys())[:count]
        variations = []

        for i in range(count):
            dim = dims[i % len(dims)]
            values = DIMENSIONS.get(dim, ["default"])
            value = values[i % len(values)]

            base_prompt = fallback_optimize(self.idea, self.target)
            # Apply simple transformations based on dimension
            modified = _apply_dimension(base_prompt, dim, value)

            variations.append(
                Variation(
                    dimension=dim,
                    value=value,
                    prompt=modified,
                )
            )

        return variations

    def to_dict(self) -> dict:
        return {
            "idea": self.idea,
            "target": self.target,
            "variations": [v.to_dict() for v in self.variations],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VibeEngine":
        engine = cls(idea=data["idea"], target=data.get("target", "general"))
        engine.variations = [Variation.from_dict(v) for v in data.get("variations", [])]
        return engine


def _apply_dimension(prompt: str, dimension: str, value: str) -> str:
    """Apply a deep dimension transformation to a template-generated prompt.

    Instead of just inserting a constraint line, this rewrites the prompt's
    Role, Output Format, and structure to genuinely reflect the dimension.
    """
    sections = _parse_sections(prompt)

    if dimension == "tone":
        sections = _apply_tone(sections, value)
    elif dimension == "audience":
        sections = _apply_audience(sections, value)
    elif dimension == "format":
        sections = _apply_format(sections, value)
    elif dimension == "specificity":
        sections = _apply_specificity(sections, value)
    elif dimension == "style":
        sections = _apply_style(sections, value)
    else:
        sections["Style Constraint"] = f"Adjust {dimension} to: {value}."

    return _render_sections(sections)


def _parse_sections(prompt: str) -> Dict[str, str]:
    """Parse a markdown prompt into {header: content} dict."""
    sections: Dict[str, str] = {}
    current_header = "_preamble"
    lines: List[str] = []

    for line in prompt.splitlines():
        if line.startswith("# "):
            if lines:
                sections[current_header] = "\n".join(lines).strip()
            current_header = line[2:].strip()
            lines = []
        else:
            lines.append(line)

    if lines:
        sections[current_header] = "\n".join(lines).strip()

    return sections


def _render_sections(sections: Dict[str, str]) -> str:
    """Render sections dict back to markdown."""
    parts = []
    for header, content in sections.items():
        if header == "_preamble":
            if content:
                parts.append(content)
        else:
            parts.append(f"# {header}\n{content}")
    return "\n\n".join(parts)


def _apply_tone(sections: Dict[str, str], value: str) -> Dict[str, str]:
    """Rewrite the prompt to reflect a specific tone."""
    tone_roles = {
        "formal": "You are a distinguished professional with deep expertise. Communicate with precision, clarity, and authority. Avoid colloquialisms.",
        "casual": "You're a friendly, knowledgeable helper. Keep things relaxed and approachable — like explaining to a friend over coffee.",
        "technical": "You are a senior technical specialist. Use precise terminology, reference standards and specifications, and assume the reader values accuracy over accessibility.",
        "playful": "You're an enthusiastic guide who makes everything fun and engaging! Use humor, analogies, and creative examples to make concepts click.",
        "authoritative": "You are a recognized authority in this domain. Speak with confidence, cite best practices, and provide definitive guidance — not suggestions.",
        "empathetic": "You are a supportive mentor who understands the challenges involved. Acknowledge difficulties, provide encouragement, and guide with patience.",
    }
    tone_formats = {
        "formal": "Provide a structured, professional response with clear sections and formal language.",
        "casual": "Keep the response conversational and easy to scan. Use short paragraphs.",
        "technical": "Use precise technical language. Include specifications, parameters, and technical references.",
        "playful": "Make the response engaging and fun to read. Use analogies, emoji-free humor, and creative examples.",
        "authoritative": "Provide definitive, well-structured guidance. Use clear imperatives and best-practice recommendations.",
        "empathetic": "Write with warmth and understanding. Acknowledge complexity and provide step-by-step support.",
    }
    if value in tone_roles:
        sections["Role"] = tone_roles[value]
    if value in tone_formats and "Output Format" in sections:
        sections["Output Format"] = tone_formats[value]
    return sections


def _apply_audience(sections: Dict[str, str], value: str) -> Dict[str, str]:
    """Rewrite the prompt to target a specific audience."""
    audience_context = {
        "beginner": "The reader is a complete beginner with no prior knowledge. Define all terms. Use simple analogies. Avoid jargon entirely. Build up from first principles.",
        "expert": "The reader is a domain expert. Skip fundamentals. Focus on nuances, edge cases, trade-offs, and advanced patterns. Use technical terminology freely.",
        "executive": "The reader is a C-level executive making decisions. Lead with impact and business value. Quantify where possible. Keep it high-level with an option to drill down.",
        "child": "The reader is a curious 10-year-old. Use simple words, fun comparisons, and real-world analogies. Make complex ideas feel like an adventure.",
        "developer": "The reader is an experienced software developer. Include code snippets, API references, and implementation details. Focus on practical, copy-paste-ready guidance.",
        "general": "The reader has mixed expertise levels. Define key terms on first use but don't over-explain. Balance accessibility with depth.",
    }
    audience_formats = {
        "beginner": "Use short sentences, numbered steps, and concrete examples for every concept. Include a glossary of key terms at the end.",
        "expert": "Dense, information-rich format. Use bullet points for key insights. Include trade-off tables and decision matrices where relevant.",
        "executive": "Start with a 2-sentence executive summary. Use bullet points for key findings. End with clear recommendations and next steps.",
        "child": 'Use short, fun paragraphs. Include "Try it!" activities. Use comparisons to things kids know (games, animals, toys).',
        "developer": "Include fenced code blocks for all examples. Use inline `code` for technical terms. Structure as a reference guide.",
        "general": "Use clear headings, mix of prose and bullets. Include examples that don't require specialized knowledge.",
    }
    if value in audience_context:
        sections["Context"] = audience_context[value]
    if value in audience_formats:
        sections["Output Format"] = audience_formats[value]
    return sections


def _apply_format(sections: Dict[str, str], value: str) -> Dict[str, str]:
    """Rewrite the Output Format section to match the desired format."""
    format_specs = {
        "prose": "Write in flowing, connected prose paragraphs. Use transitions between ideas. No bullet points or numbered lists — let the narrative flow naturally.",
        "bullets": "Use bullet points throughout:\n- Main points as top-level bullets\n- Supporting details as nested bullets\n- Each bullet is one clear, self-contained point\n- No prose paragraphs — everything is bulleted",
        "step-by-step": "Structure as a numbered step-by-step guide:\n1. Each step is a single, actionable instruction\n2. Steps are ordered by dependency (do X before Y)\n3. Include expected outcome after each step\n4. Add troubleshooting tips for steps that commonly fail",
        "code": 'Provide working code examples for every concept:\n- Each code block is fenced with the language specified\n- Include inline comments explaining the "why"\n- Show both the implementation and a usage example\n- All code must be copy-paste-ready and runnable',
        "dialogue": "Frame the response as a Q&A dialogue:\n- Q: (common question about the topic)\n- A: (clear, direct answer)\n- Follow-up Q: (digging deeper)\n- Use this format to cover all key aspects naturally",
        "report": "Structure as a formal report:\n1. **Executive Summary** — 2-3 sentence overview\n2. **Background** — Context and scope\n3. **Findings** — Detailed analysis with evidence\n4. **Recommendations** — Actionable next steps\n5. **Appendix** — Supporting details and references",
    }
    if value in format_specs:
        sections["Output Format"] = format_specs[value]
    return sections


def _apply_specificity(sections: Dict[str, str], value: str) -> Dict[str, str]:
    """Adjust the specificity level of the prompt."""
    task = sections.get("Task", "")

    specificity_mods = {
        "broad": (
            f"Explore the full breadth of: {task}\n\n"
            f"Cover multiple angles, approaches, and perspectives. "
            f"Don't commit to one path — survey the landscape and highlight trade-offs between options."
        ),
        "narrow": (
            f"Focus deeply on the single most critical aspect of: {task}\n\n"
            f"Identify the #1 priority and go deep. Ignore tangential concerns. "
            f"Provide exhaustive detail on this one thing."
        ),
        "exploratory": (
            f"Take an exploratory approach to: {task}\n\n"
            f"Raise open questions. Propose hypotheses. Identify unknowns and risks. "
            f"Map out what we know vs. what we'd need to investigate further."
        ),
        "precise": (
            f"Be maximally precise about: {task}\n\n"
            f"Every claim must be specific and verifiable. Use exact numbers, names, "
            f'and references. Avoid hedging language ("might", "could", "generally"). '
            f"If something is uncertain, state the confidence level explicitly."
        ),
    }
    if value in specificity_mods:
        sections["Task"] = specificity_mods[value]
    return sections


def _apply_style(sections: Dict[str, str], value: str) -> Dict[str, str]:
    """Adjust the writing style of the prompt."""
    style_roles = {
        "concise": "You are a precise communicator. Every word earns its place. Cut ruthlessly — if a sentence doesn't add value, delete it.",
        "verbose": "You are a thorough expert who leaves nothing unexplained. Cover every angle, provide detailed examples, and anticipate follow-up questions.",
        "academic": "You are a scholarly researcher. Use formal academic language, cite established frameworks, and structure arguments with clear thesis/evidence/conclusion patterns.",
        "conversational": 'You\'re a knowledgeable colleague having an informal discussion. Use "you" and "we". Share anecdotes. Be direct but warm.',
        "poetic": "You are an eloquent communicator who finds beauty in ideas. Use vivid imagery, metaphors, and rhythmic language to make concepts memorable.",
    }
    style_constraints = {
        "concise": "Maximum 3 sentences per section. No filler words. No restating what was already said. If you can say it in 5 words, don't use 10.",
        "verbose": "Provide thorough explanations for every point. Include multiple examples. Anticipate and address potential questions. Leave no concept unexplained.",
        "academic": "Use formal language. Reference established methodologies. Structure as: claim → evidence → analysis. Include a conclusion that synthesizes findings.",
        "conversational": 'Write like you\'re talking to a friend. Use contractions. Ask rhetorical questions. Share the "why" behind recommendations, not just the "what".',
        "poetic": "Paint pictures with words. Use metaphors to illuminate complex ideas. Let rhythm and cadence carry the reader through the response.",
    }
    if value in style_roles:
        sections["Role"] = style_roles[value]
    if value in style_constraints:
        sections["Requirements"] = style_constraints.get(value, sections.get("Requirements", ""))
    return sections
