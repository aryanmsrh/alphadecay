import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_investigation_chart(
    ticker: str,
    quarterly_history: List[Dict[str, Any]],
    output_path: str
) -> str:
    if not quarterly_history:
        periods = ["Q1", "Q2", "Q3", "Q4"]
        sales = [100.0, 110.0, 120.0, 125.0]
        margins = [20.0, 21.0, 19.5, 20.5]
    else:
        periods = [item["period"] for item in quarterly_history]
        sales = [item.get("revenue") or 0.0 for item in quarterly_history]
        margins = [item.get("operating_margin_pct") or 0.0 for item in quarterly_history]

    fig, ax1 = plt.subplots(figsize=(8.0, 3.8), dpi=160)
    plt.subplots_adjust(bottom=0.20, top=0.88, left=0.10, right=0.90)

    color_sales = "#1E3A8A"
    color_margin = "#059669"

    x_indices = range(len(periods))
    bars = ax1.bar(x_indices, sales, width=0.45, color=color_sales, alpha=0.85, label="Net Sales (₹ Cr)")
    ax1.set_ylabel("Net Sales (₹ Cr)", color=color_sales, fontsize=9, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=color_sales, labelsize=8)
    ax1.set_xticks(x_indices)
    ax1.set_xticklabels(periods, rotation=15, ha="right", fontsize=8)
    ax1.grid(axis="y", linestyle="--", alpha=0.3)

    ax2 = ax1.twinx()
    lines = ax2.plot(x_indices, margins, color=color_margin, marker="o", linewidth=2.0, label="Operating Margin (%)")
    ax2.set_ylabel("Operating Margin (%)", color=color_margin, fontsize=9, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=color_margin, labelsize=8)

    plt.title(f"{ticker.upper()} — Revenue & Operating Margin Trajectory", fontsize=10, fontweight="bold", pad=10)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out), bbox_inches="tight")
    plt.close(fig)

    return str(out)
