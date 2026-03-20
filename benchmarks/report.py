"""Human-readable benchmark report formatting."""

from __future__ import annotations

from typing import Dict, List


def format_report(report: dict) -> str:
    """Format a benchmark report dict as a human-readable terminal string."""
    lines: list[str] = []
    summary = report.get("summary", {})

    # ── Header ──────────────────────────────────────────────────────────
    lines.append("")
    lines.append("  Prompt Master — Benchmark Report")
    lines.append("  " + "═" * 50)
    lines.append(f"  Date:    {summary.get('timestamp', 'N/A')[:19]}")
    lines.append(f"  Cases:   {summary.get('total_cases', 0)}")
    lines.append(f"  Domains: {', '.join(summary.get('domains', []))}")
    lines.append("")

    # ── Per-case results ────────────────────────────────────────────────
    cases = report.get("cases", [])

    # Group by domain
    by_domain: Dict[str, list] = {}
    for c in cases:
        d = c.get("domain", "general")
        by_domain.setdefault(d, []).append(c)

    for domain, domain_cases in sorted(by_domain.items()):
        lines.append(f"  ── {domain.upper()} ──")
        lines.append("")

        for c in domain_cases:
            structural = c.get("structural", {})
            pct = structural.get("pct", 0) if structural else 0
            bar = _progress_bar(pct)
            elapsed = c.get("elapsed_ms", 0)
            api_tag = "API" if c.get("used_api") else "TPL"

            lines.append(
                f"  {c['case_id']:>8s}  {bar} {pct:5.1f}%  "
                f"[{api_tag}] {elapsed:6.0f}ms  {c.get('case_name', '')}"
            )

            # Show judge score if available
            judge = c.get("judge")
            if judge and judge.get("avg_score", 0) > 0:
                lines.append(
                    f"           Judge: {judge['avg_score']:.1f}/5.0  "
                    f"({judge.get('summary', '')})"
                )

            # Show failed checks
            if structural:
                failed = [
                    ch for ch in structural.get("checks", [])
                    if not ch.get("passed")
                ]
                for ch in failed:
                    lines.append(f"           FAIL  {ch['name']}: {ch.get('detail', '')}")

        lines.append("")

    # ── Summary ─────────────────────────────────────────────────────────
    lines.append("  ── SUMMARY ──")
    lines.append(f"  Structural avg: {summary.get('avg_structural_pct', 0):.1f}%")
    if "avg_judge_score" in summary:
        lines.append(f"  Judge avg:      {summary['avg_judge_score']:.2f}/5.0")
    lines.append("")

    return "\n".join(lines)


def format_comparison(report_a: dict, report_b: dict, label_a: str = "A", label_b: str = "B") -> str:
    """Format a side-by-side comparison of two benchmark runs."""
    lines: list[str] = []

    cases_a = {c["case_id"]: c for c in report_a.get("cases", [])}
    cases_b = {c["case_id"]: c for c in report_b.get("cases", [])}

    all_ids = sorted(set(cases_a) | set(cases_b))

    lines.append("")
    lines.append(f"  Benchmark Comparison: [{label_a}] vs [{label_b}]")
    lines.append("  " + "═" * 50)
    lines.append(f"  {'Case':>10s}  {label_a:>8s}  {label_b:>8s}  {'Delta':>8s}")
    lines.append("  " + "─" * 40)

    total_a = 0.0
    total_b = 0.0
    count = 0

    for cid in all_ids:
        ca = cases_a.get(cid, {})
        cb = cases_b.get(cid, {})
        pct_a = ca.get("structural", {}).get("pct", 0) if ca else 0
        pct_b = cb.get("structural", {}).get("pct", 0) if cb else 0
        delta = pct_b - pct_a
        sign = "+" if delta > 0 else ""

        lines.append(f"  {cid:>10s}  {pct_a:7.1f}%  {pct_b:7.1f}%  {sign}{delta:.1f}%")
        total_a += pct_a
        total_b += pct_b
        count += 1

    if count:
        avg_a = total_a / count
        avg_b = total_b / count
        delta = avg_b - avg_a
        sign = "+" if delta > 0 else ""
        lines.append("  " + "─" * 40)
        lines.append(f"  {'AVG':>10s}  {avg_a:7.1f}%  {avg_b:7.1f}%  {sign}{delta:.1f}%")

    lines.append("")
    return "\n".join(lines)


def _progress_bar(pct: float, width: int = 20) -> str:
    """Render a text-based progress bar."""
    filled = int(width * pct / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"
