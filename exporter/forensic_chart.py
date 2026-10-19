import sys
import uuid
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless CLI / server execution
import matplotlib.pyplot as plt
from engine.models import ForensicSummary
from exporter.theme import (
    HEX_BG_SECONDARY, HEX_BG_CARD, HEX_TEXT_PRIMARY, HEX_TEXT_SECONDARY,
    HEX_TEXT_MUTED, HEX_ACCENT_GREEN, HEX_ACCENT_RED, HEX_ACCENT_BLUE,
    HEX_ACCENT_YELLOW, HEX_BORDER
)

def generate_forensic_chart(summary: ForensicSummary, output_path: Optional[str] = None) -> str:
    """
    Generates an institutional dark-theme dual-panel historical forensic ratio chart.
    Strictly backward-looking historical audit data (Zero future predictions).
    
    Panel 1: Historical Reported Sales Growth YoY (%) vs Expense-Adjusted Revenue Growth Residual (Heuristic %)
             Highlights the divergence where top-line growth diverged from cost-adjusted realization proxy.
    Panel 2: Historical Debtor Days Trend Line showing distributor credit velocity against screening benchmark.
    """
    ticker = summary.ticker.upper()
    periods = summary.quarters_analyzed
    if not periods:
        periods = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]

    # Convert values, handling None as np.nan
    raw_sales_growth = [summary.sales_growth_yoy.get(p) for p in periods]
    sales_growth = [float(val) if val is not None and not np.isnan(float(val)) else np.nan for val in raw_sales_growth]
    
    raw_residual = [summary.expense_adjusted_residual.get(p) for p in periods]
    residual = [float(val) if val is not None and not np.isnan(float(val)) else np.nan for val in raw_residual]
    
    raw_debtor_days = [summary.debtor_days.get(p) for p in periods]
    debtor_days = [float(val) if val is not None and not np.isnan(float(val)) else np.nan for val in raw_debtor_days]

    # Setup unique default output path in data directory to prevent collisions
    if not output_path:
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        unique_id = uuid.uuid4().hex[:8]
        output_path = str(data_dir / f"forensic_chart_{ticker}_{unique_id}.png")

    chart_rc = {
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 8.0,
        "axes.edgecolor": HEX_BORDER,
        "axes.linewidth": 0.8,
        "xtick.color": HEX_TEXT_SECONDARY,
        "ytick.color": HEX_TEXT_SECONDARY,
        "text.color": HEX_TEXT_PRIMARY,
        "figure.facecolor": HEX_BG_SECONDARY,
        "axes.facecolor": HEX_BG_CARD
    }

    with plt.rc_context(chart_rc):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.2, 4.4), sharex=True, dpi=200)
        fig.patch.set_facecolor(HEX_BG_SECONDARY)
        plt.subplots_adjust(hspace=0.28, left=0.08, right=0.96, top=0.92, bottom=0.14)

        try:
            # --- PANEL 1: Sales YoY vs Expense-Adjusted Revenue Residual ---
            ax1.set_facecolor(HEX_BG_CARD)
            ax1.plot(periods, sales_growth, color=HEX_ACCENT_BLUE, marker="o", markersize=4.5,
                     linewidth=1.8, label="Reported Net Sales YoY (%)")
            ax1.plot(periods, residual, color=HEX_ACCENT_YELLOW, marker="s", markersize=4.0,
                     linestyle="--", linewidth=1.6, label="Expense-Adjusted Revenue Residual (Heuristic %)")
            
            # Shade divergence spread where both are valid numbers
            valid_mask = [not np.isnan(s) and not np.isnan(r) for s, r in zip(sales_growth, residual)]
            if any(valid_mask):
                where_clause = [(s >= r if (not np.isnan(s) and not np.isnan(r)) else False) for s, r in zip(sales_growth, residual)]
                ax1.fill_between(
                    periods, sales_growth, residual,
                    where=where_clause,
                    color=HEX_ACCENT_YELLOW, alpha=0.12, label="Cost Residual Divergence Spread"
                )
            
            ax1.axhline(0.0, color=HEX_BORDER, linestyle=":", linewidth=1.0)
            ax1.set_title(f"{ticker} — Trailing Net Sales Growth vs Expense Residual (Screening Heuristic)", 
                          fontsize=8.5, fontweight="bold", color=HEX_TEXT_PRIMARY, pad=5, loc="left")
            ax1.set_ylabel("Growth Rate (%)", fontsize=7.5, fontweight="bold", color=HEX_TEXT_SECONDARY)
            ax1.grid(True, linestyle="--", alpha=0.35, color=HEX_BORDER)
            leg1 = ax1.legend(loc="upper left", fontsize=6.8, frameon=True,
                              facecolor=HEX_BG_SECONDARY, edgecolor=HEX_BORDER)
            for text in leg1.get_texts():
                text.set_color(HEX_TEXT_PRIMARY)
            ax1.tick_params(axis="both", labelsize=7.5)

            # --- PANEL 2: Debtor Days Working Capital Velocity ---
            ax2.set_facecolor(HEX_BG_CARD)
            # Choose color based on trend: if compressed/accelerated = GREEN, if elongated = RED
            valid_d = [d for d in debtor_days if not np.isnan(d)]
            dd_color = HEX_ACCENT_BLUE
            if len(valid_d) >= 2:
                dd_color = HEX_ACCENT_GREEN if valid_d[-1] <= valid_d[0] else HEX_ACCENT_RED

            ax2.plot(periods, debtor_days, color=dd_color, marker="D", markersize=5.0,
                     linewidth=2.0, label="Debtor Days (Audited Balance Sheet Ratio)")
            
            # Fill strictly where values are valid
            debtor_mask = [not np.isnan(d) for d in debtor_days]
            if any(debtor_mask):
                ax2.fill_between(periods, debtor_days, 0, where=debtor_mask, color=dd_color, alpha=0.10)
            
            # Screening reference threshold
            ref_threshold = getattr(summary, "debtor_days_threshold", 22.0) or 22.0
            ax2.axhline(ref_threshold, color=HEX_ACCENT_RED, linestyle="--", linewidth=1.1,
                        alpha=0.75, label=f"Sector Screening Reference ({ref_threshold:.0f}d)")
            
            ax2.set_title(f"{ticker} — Historical Debtor Days & Trade Credit Velocity (Statutory Disclosures)", 
                          fontsize=8.5, fontweight="bold", color=HEX_TEXT_PRIMARY, pad=5, loc="left")
            ax2.set_ylabel("Days Sales (d)", fontsize=7.5, fontweight="bold", color=HEX_TEXT_SECONDARY)
            ax2.set_xlabel("Statutory Reporting Quarters", fontsize=7.5, fontweight="bold", color=HEX_TEXT_SECONDARY)
            ax2.grid(True, linestyle="--", alpha=0.35, color=HEX_BORDER)
            leg2 = ax2.legend(loc="upper left", fontsize=6.8, frameon=True,
                              facecolor=HEX_BG_SECONDARY, edgecolor=HEX_BORDER)
            for text in leg2.get_texts():
                text.set_color(HEX_TEXT_PRIMARY)
            ax2.tick_params(axis="both", labelsize=7.5)
            ax2.tick_params(axis="x", rotation=15)

            # Save figure with dark padding
            fig.savefig(output_path, bbox_inches="tight", dpi=200, facecolor=fig.get_facecolor(), edgecolor="none")
        finally:
            plt.close(fig)

    return output_path
