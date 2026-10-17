import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import matplotlib
matplotlib.use("Agg") # Non-interactive backend for headless CLI / server execution
import matplotlib.pyplot as plt
from engine.models import ForensicSummary

def generate_forensic_chart(summary: ForensicSummary, output_path: Optional[str] = None) -> str:
    """
    Generates an institutional dual-panel historical forensic ratio chart.
    Strictly backward-looking historical audit data (Zero future predictions).
    
    Panel 1: Historical Reported Sales Growth YoY (%) vs Derived Underlying Volume Growth (UVG %)
             Highlights the realization wedge where headline growth masked unit volume softening.
    Panel 2: Historical Debtor Days Trend Line showing distributor credit expansion.
    """
    ticker = summary.ticker.upper()
    periods = summary.quarters_analyzed
    if not periods:
        periods = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]

    sales_growth = [summary.sales_growth_yoy.get(p, 0.0) for p in periods]
    volume_growth = [summary.derived_volume_growth.get(p, 0.0) for p in periods]
    debtor_days = [summary.debtor_days.get(p, 20.0) for p in periods]

    # Setup default output path in data directory
    if not output_path:
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(data_dir / f"forensic_chart_{ticker}.png")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.2, 4.6), sharex=True, dpi=200)
    plt.subplots_adjust(hspace=0.28)

    # Styling settings
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans", "font.size": 8.5})

    # --- PANEL 1: Sales YoY vs Derived Volume Growth ---
    ax1.plot(periods, sales_growth, color="#1E3A8A", marker="o", linewidth=2.0, label="Reported Net Sales YoY (%)")
    ax1.plot(periods, volume_growth, color="#DC2626", marker="s", linestyle="--", linewidth=1.8, label="Derived Underlying Volume Growth (%)")
    
    # Shade the realization divergence wedge
    ax1.fill_between(periods, sales_growth, volume_growth, where=[s >= v for s, v in zip(sales_growth, volume_growth)],
                     color="#FCA5A5", alpha=0.35, label="Realization Wedge (P vs Q)")
    
    ax1.axhline(0.0, color="#6B7280", linestyle=":", linewidth=1.0)
    ax1.set_title(f"{ticker} - Historical Revenue vs Derived Volume Growth (Historical Forensic Decomposition)", 
                  fontsize=9.5, fontweight="bold", color="#111827", pad=6)
    ax1.set_ylabel("Growth Rate (%)", fontsize=8, fontweight="bold", color="#374151")
    ax1.grid(True, linestyle="--", alpha=0.45)
    ax1.legend(loc="upper left", fontsize=7.5, frameon=True, facecolor="#F9FAFB", edgecolor="#E5E7EB")
    ax1.tick_params(axis="both", labelsize=8)

    # --- PANEL 2: Debtor Days Working Capital Velocity ---
    ax2.plot(periods, debtor_days, color="#0D9488", marker="D", linewidth=2.2, label="Debtor Days (Turnover Velocity)")
    ax2.fill_between(periods, debtor_days, 0, color="#99F6E4", alpha=0.25)
    ax2.axhline(22.0, color="#EF4444", linestyle="--", linewidth=1.2, label="FMCG Working Capital Warning (22d)")
    
    ax2.set_title(f"{ticker} - Historical Debtor Days Elongation (Channel Credit Velocity)", 
                  fontsize=9.5, fontweight="bold", color="#111827", pad=6)
    ax2.set_ylabel("Days Sales (d)", fontsize=8, fontweight="bold", color="#374151")
    ax2.set_xlabel("Statutory Reporting Quarters", fontsize=8, fontweight="bold", color="#374151")
    ax2.grid(True, linestyle="--", alpha=0.45)
    ax2.legend(loc="upper left", fontsize=7.5, frameon=True, facecolor="#F9FAFB", edgecolor="#E5E7EB")
    ax2.tick_params(axis="both", labelsize=8)
    ax2.tick_params(axis="x", rotation=22)

    # Save figure
    fig.savefig(output_path, bbox_inches="tight", dpi=200)
    plt.close(fig)

    return output_path

if __name__ == "__main__":
    from ingestion.screener import ScreenerScraper
    from engine.forensics import ForensicEngine
    
    scraper = ScreenerScraper()
    raw = scraper.fetch_company_data("HINDUNILVR")
    summary = ForensicEngine.audit_company(raw)
    chart_file = generate_forensic_chart(summary)
    print(f"Forensic dual-panel chart generated successfully: {chart_file}")
