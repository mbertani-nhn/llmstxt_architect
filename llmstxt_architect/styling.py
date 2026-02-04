"""
Terminal styling utilities for LLMsTxt Architect.
"""

from typing import Any, Dict

ANSI_COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "reset": "\033[0m",
}

STATUS_PREFIXES = {
    "processing": ("blue", "[...]"),
    "info": ("blue", "[i]"),
    "error": ("red", "[!]"),
    "success": ("green", "[✓]"),
}


def color_text(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    code = ANSI_COLORS.get(color, "")
    reset = ANSI_COLORS["reset"]
    if not code:
        return text
    return f"{code}{text}{reset}"


def draw_box(text: str, color: str, padding: int = 1) -> str:
    """Draw a box around text using Unicode box-drawing characters."""
    pad = " " * padding
    inner = f"{pad}{text}{pad}"
    width = len(inner)
    top = "┌" + "─" * width + "┐"
    mid = "│" + inner + "│"
    bot = "└" + "─" * width + "┘"
    return f"{top}\n{mid}\n{bot}"


def status_message(text: str, status_type: str) -> str:
    """Format a status message with a colored prefix."""
    color, prefix = STATUS_PREFIXES.get(status_type, ("blue", "[i]"))
    return f"{color_text(prefix, color)} {text}"


def generate_summary_report(stats: Dict[str, Any]) -> str:
    """Generate a summary report from processing stats."""
    lines = [
        color_text("─── Summary Report ───", "green"),
        f"  URLs processed:      {stats.get('urls_processed', 0)}",
        f"  Summaries generated: {stats.get('summaries_generated', 0)}",
        f"  Total time:          {stats.get('total_time', 0):.1f}s",
        f"  Output:              {stats.get('output_path', '')}",
    ]
    failed = stats.get("failed_urls", [])
    if failed:
        lines.append(color_text(f"  Failed URLs:         {len(failed)}", "yellow"))
        for url in failed:
            lines.append(color_text(f"    - {url}", "yellow"))
    return "\n".join(lines)
