from pathlib import Path
from typing import Any, Dict, List, Union

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_investigation_chart(
    arg1: Union[str, List[Dict[str, Any]]],
    arg2: Union[str, List[Dict[str, Any]]],
    output_path: str,
) -> str:
  if isinstance(arg1, list):
    quarterly_history = arg1
    ticker = str(arg2)
  else:
    ticker = str(arg1)
    quarterly_history = arg2 if isinstance(arg2, list) else []

  valid_items = [
      item
      for item in quarterly_history
      if item.get("revenue") is not None
      or item.get("operating_margin_pct") is not None
  ]

  plt.style.use("dark_background")
  fig, ax1 = plt.subplots(figsize=(8.0, 3.8), dpi=160)
  fig.patch.set_facecolor("#070709")
  ax1.set_facecolor("#0A0A0E")
  plt.subplots_adjust(bottom=0.20, top=0.88, left=0.10, right=0.90)

  color_sales = "#38BDF8"
  color_margin = "#22C55E"

  if valid_items:
    periods = [
        str(item.get("period", f"P{i+1}"))
        for i, item in enumerate(valid_items)
    ]
    sales = [float(item.get("revenue") or 0.0) for item in valid_items]
    margins = [
        float(item.get("operating_margin_pct") or 0.0) for item in valid_items
    ]

    x_indices = range(len(periods))
    ax1.bar(
        x_indices,
        sales,
        width=0.45,
        color=color_sales,
        alpha=0.85,
        label="Net Sales (₹ Cr)",
    )
    ax1.set_ylabel(
        "Net Sales (₹ Cr)", color=color_sales, fontsize=8.5, fontweight="bold"
    )
    ax1.tick_params(axis="y", labelcolor=color_sales, labelsize=7.5)
    ax1.set_xticks(list(x_indices))
    ax1.set_xticklabels(
        periods, rotation=15, ha="right", fontsize=7.5, color="#A1A1AA"
    )
    ax1.grid(axis="y", linestyle="--", color="#27272A", alpha=0.5)

    ax2 = ax1.twinx()
    ax2.plot(
        x_indices,
        margins,
        color=color_margin,
        marker="o",
        markersize=4.5,
        linewidth=2.0,
        label="Operating Margin (%)",
    )
    ax2.set_ylabel(
        "Operating Margin (%)",
        color=color_margin,
        fontsize=8.5,
        fontweight="bold",
    )
    ax2.tick_params(axis="y", labelcolor=color_margin, labelsize=7.5)

    for spine in ax2.spines.values():
      spine.set_color("#27272A")
  else:
    ax1.text(
        0.5,
        0.5,
        "No Quarterly Series Available in Filing",
        horizontalalignment="center",
        verticalalignment="center",
        transform=ax1.transAxes,
        color="#A1A1AA",
        fontsize=10,
    )

  for spine in ax1.spines.values():
    spine.set_color("#27272A")

  plt.title(
      f"{ticker.upper()} — Revenue & Operating Margin Trajectory",
      fontsize=9.5,
      fontweight="bold",
      color="#F4F4F6",
      pad=10,
  )

  out = Path(output_path)
  out.parent.mkdir(parents=True, exist_ok=True)
  plt.savefig(
      str(out),
      bbox_inches="tight",
      facecolor=fig.get_facecolor(),
      edgecolor="none",
  )
  plt.close(fig)

  return str(out)