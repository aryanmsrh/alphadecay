"""
ALPHA-DECAY: Centralized Institutional Dark Theme & Visual Token System.
Unified visual tokens, palettes, semantic colors, and typography rules
for dark financial-terminal research notes and dual-panel charts.
"""

from typing import Optional, Tuple, Any
from reportlab.lib import colors

# ==============================================================================
# 1. CORE COLOR PALETTE (Hex and ReportLab Color Tokens)
# ==============================================================================

# Backgrounds
HEX_BG_PRIMARY = "#05070A"      # Deep terminal black
HEX_BG_SECONDARY = "#0D1117"    # Dark graphite panel background
HEX_BG_CARD = "#121922"         # Elevated card / row background
HEX_BG_CARD_ALT = "#161F2B"     # Alternating table row background

# Typography
HEX_TEXT_PRIMARY = "#F3F6FA"    # Soft crisp white
HEX_TEXT_SECONDARY = "#9AA8B7"  # Cool technical gray
HEX_TEXT_MUTED = "#5A6878"      # Darker timestamp / disclaimer gray

# Semantic Accents
HEX_ACCENT_GREEN = "#39D98A"    # Bright positive / favorable movement
HEX_ACCENT_RED = "#FF5964"      # Clear adverse / negative movement
HEX_ACCENT_BLUE = "#58A6FF"     # Electric blue: informational, links, headers
HEX_ACCENT_YELLOW = "#F5C84C"   # Vivid caution, caveats, missing data (N/A)

HEX_GREEN_BENIGN = HEX_ACCENT_GREEN
HEX_RED_ADVERSE = HEX_ACCENT_RED
HEX_BLUE_ACCENT = HEX_ACCENT_BLUE
HEX_YELLOW_ALERT = HEX_ACCENT_YELLOW

# Borders & Structural Rules
HEX_BORDER = "#273241"          # Muted graphite line / grid
HEX_BORDER_LIGHT = "#354354"    # Subtle divider rule
HEX_BORDER_ACCENT = "#58A6FF"   # Hero accent rule

# ReportLab Color Objects
COLOR_BG_PRIMARY = colors.HexColor(HEX_BG_PRIMARY)
COLOR_BG_SECONDARY = colors.HexColor(HEX_BG_SECONDARY)
COLOR_BG_CARD = colors.HexColor(HEX_BG_CARD)
COLOR_BG_CARD_ALT = colors.HexColor(HEX_BG_CARD_ALT)

COLOR_TEXT_PRIMARY = colors.HexColor(HEX_TEXT_PRIMARY)
COLOR_TEXT_SECONDARY = colors.HexColor(HEX_TEXT_SECONDARY)
COLOR_TEXT_MUTED = colors.HexColor(HEX_TEXT_MUTED)

COLOR_ACCENT_GREEN = colors.HexColor(HEX_ACCENT_GREEN)
COLOR_ACCENT_RED = colors.HexColor(HEX_ACCENT_RED)
COLOR_ACCENT_BLUE = colors.HexColor(HEX_ACCENT_BLUE)
COLOR_ACCENT_YELLOW = colors.HexColor(HEX_ACCENT_YELLOW)

COLOR_BORDER = colors.HexColor(HEX_BORDER)
COLOR_BORDER_LIGHT = colors.HexColor(HEX_BORDER_LIGHT)
COLOR_BORDER_ACCENT = colors.HexColor(HEX_BORDER_ACCENT)


# ==============================================================================
# 2. CONTEXTUAL DIRECTION & SEMANTIC COLOR RESOLUTION
# ==============================================================================

def get_semantic_color(
    metric_name_or_val: Any,
    val: Optional[float] = None,
    unit: str = "",
    explicit_direction: Optional[str] = None,
    higher_is_better: Optional[bool] = None
) -> Tuple[str, colors.Color]:
    """
    Returns (hex_code, reportlab_color) based on economic reality, not raw sign.
    
    Economic Logic:
    - Debtor Days: Lower is favorable (Green), higher is adverse (Red).
    - Operating Margin Delta: Positive is favorable (Green), negative is adverse (Red).
    - Net Sales Growth: Positive is favorable (Green), negative is adverse (Red).
    - Distribution Drag (Exp/Sales): Expansion is adverse (Red), compression is favorable (Green).
    - Missing / N/A: Vivid Yellow.
    """
    if isinstance(metric_name_or_val, (int, float)) and val is None:
        val = float(metric_name_or_val)
        metric_name = ""
    else:
        metric_name = str(metric_name_or_val or "")

    if val is None:
        return HEX_ACCENT_YELLOW, COLOR_ACCENT_YELLOW

    # 1. Use higher_is_better if explicitly provided
    if higher_is_better is not None:
        if higher_is_better:
            if val > 0:
                return HEX_ACCENT_GREEN, COLOR_ACCENT_GREEN
            elif val < 0:
                return HEX_ACCENT_RED, COLOR_ACCENT_RED
        else:
            if val > 0:
                return HEX_ACCENT_RED, COLOR_ACCENT_RED
            elif val < 0:
                return HEX_ACCENT_GREEN, COLOR_ACCENT_GREEN
        return HEX_TEXT_PRIMARY, COLOR_TEXT_PRIMARY

    # 2. Use explicit direction if provided by ForensicEngine
    if explicit_direction:
        d = explicit_direction.lower()
        if d in ("favorable", "positive", "supported"):
            return HEX_ACCENT_GREEN, COLOR_ACCENT_GREEN
        if d in ("adverse", "negative", "deterioration", "refuted"):
            return HEX_ACCENT_RED, COLOR_ACCENT_RED
        if d in ("neutral", "screening"):
            return HEX_ACCENT_BLUE, COLOR_ACCENT_BLUE
        if d in ("warning", "caution", "not_established"):
            return HEX_ACCENT_YELLOW, COLOR_ACCENT_YELLOW

    m_lower = metric_name.lower()

    # 3. Debtor Days context: negative delta = cash accelerated = GREEN
    if "debtor" in m_lower or "dso" in m_lower or "credit" in m_lower:
        if val < 0:
            return HEX_ACCENT_GREEN, COLOR_ACCENT_GREEN
        elif val > 0:
            return HEX_ACCENT_RED, COLOR_ACCENT_RED
        return HEX_TEXT_PRIMARY, COLOR_TEXT_PRIMARY

    # 4. Operating margin / sales growth: positive delta = favorable = GREEN
    if any(k in m_lower for k in ("margin", "sales", "revenue", "opm", "profit", "cfo")):
        if val > 0:
            return HEX_ACCENT_GREEN, COLOR_ACCENT_GREEN
        elif val < 0:
            return HEX_ACCENT_RED, COLOR_ACCENT_RED
        return HEX_TEXT_PRIMARY, COLOR_TEXT_PRIMARY

    # 5. Expense to sales / drag / cost: higher is adverse = RED
    if any(k in m_lower for k in ("expense", "drag", "cost", "cogs")):
        if val > 0:
            return HEX_ACCENT_RED, COLOR_ACCENT_RED
        elif val < 0:
            return HEX_ACCENT_GREEN, COLOR_ACCENT_GREEN
        return HEX_TEXT_PRIMARY, COLOR_TEXT_PRIMARY

    # Default fallback
    if val > 0:
        return HEX_ACCENT_GREEN, COLOR_ACCENT_GREEN
    elif val < 0:
        return HEX_ACCENT_RED, COLOR_ACCENT_RED
    return HEX_TEXT_PRIMARY, COLOR_TEXT_PRIMARY


def format_signed_metric_html(
    val: Optional[float],
    unit: str = "",
    metric_name: str = "",
    explicit_direction: Optional[str] = None,
    higher_is_better: Optional[bool] = None
) -> str:
    """
    Returns an HTML snippet with strict semantic coloring for ReportLab Paragraphs.
    E.g. <font color="#39D98A"><b>-4.0d</b></font> or <font color="#FF5964"><b>-100.0 bps</b></font>
    """
    if val is None:
        return f'<font color="{HEX_ACCENT_YELLOW}"><b>N/A</b></font>'

    hex_color, _ = get_semantic_color(metric_name, val, unit, explicit_direction, higher_is_better)
    unit_str = f" {unit}".rstrip() if unit and not unit.startswith("%") else unit

    if abs(val) < 1e-6:
        s = f"0.0{unit_str}"
    else:
        s = f"{val:+.1f}{unit_str}" if unit in ("bps", "%", "d") else f"{val:+.2f}{unit_str}"

    return f'<font color="{hex_color}"><b>{s}</b></font>'


# ==============================================================================
# 3. VERDICT VISUAL STYLES
# ==============================================================================

VERDICT_THEME = {
    "SUPPORTED": {
        "hex": HEX_ACCENT_GREEN,
        "bg_hex": "#0D281E",
        "border_hex": "#39D98A",
        "label": "SUPPORTED",
        "description": "Evidence affirmatively confirms hypothesis"
    },
    "REFUTED": {
        "hex": HEX_ACCENT_RED,
        "bg_hex": "#280D12",
        "border_hex": "#FF5964",
        "label": "REFUTED",
        "description": "Evidence or falsification condition contradicts hypothesis"
    },
    "NOT_ESTABLISHED": {
        "hex": HEX_ACCENT_YELLOW,
        "bg_hex": "#2A230D",
        "border_hex": "#F5C84C",
        "label": "NOT ESTABLISHED",
        "description": "Available evidence does not justify an affirmative conclusion"
    }
}

DATA_SUFFICIENCY_THEME = {
    "SUFFICIENT": {"hex": HEX_ACCENT_GREEN, "label": "SUFFICIENT DATA"},
    "LIMITED": {"hex": HEX_ACCENT_YELLOW, "label": "LIMITED DATA"},
    "INSUFFICIENT": {"hex": HEX_ACCENT_RED, "label": "INSUFFICIENT DATA"}
}
