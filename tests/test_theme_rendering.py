import os
import pytest
from pathlib import Path
import pymupdf as fitz
import numpy as np

from engine.models import ForensicSummary, AnomalyCandidate
from exporter.pdf_report import export_forensic_pdf
from exporter.theme import (
    HEX_BG_PRIMARY, HEX_BG_SECONDARY, HEX_BG_CARD,
    HEX_TEXT_PRIMARY, HEX_TEXT_MUTED, HEX_GREEN_BENIGN,
    HEX_RED_ADVERSE, HEX_BLUE_ACCENT, HEX_YELLOW_ALERT,
    HEX_BORDER, get_semantic_color, format_signed_metric_html
)


def test_theme_color_tokens_and_contrast():
    """Verify dark terminal tokens exist and adhere to contrast principles."""
    assert HEX_BG_PRIMARY == "#05070A"
    assert HEX_BG_SECONDARY == "#0D1117"
    assert HEX_BG_CARD == "#121922"
    assert HEX_TEXT_PRIMARY == "#F3F6FA"
    assert HEX_BORDER == "#273241"

    # Semantic color checks
    assert get_semantic_color(-100, higher_is_better=True)[0] == HEX_RED_ADVERSE
    assert get_semantic_color(100, higher_is_better=True)[0] == HEX_GREEN_BENIGN
    assert get_semantic_color(0.0)[0] == HEX_TEXT_PRIMARY

    # Formatted signed metric
    html_neg = format_signed_metric_html(-100.0, "bps", higher_is_better=True)
    assert "-100.0 bps" in html_neg
    assert HEX_RED_ADVERSE in html_neg

    html_pos = format_signed_metric_html(50.0, "bps", higher_is_better=True)
    assert "+50.0 bps" in html_pos
    assert HEX_GREEN_BENIGN in html_pos


def test_dark_pdf_rendering_and_pixel_inspection(tmp_path):
    """
    Renders a 2-page dark theme PDF, converts pages to images via PyMuPDF (fitz),
    and asserts:
    1. Background is dark (#05070A -> RGB ~ (5, 7, 10)).
    2. Text does not contain INCONCLUSIVE.
    3. Text contains NOT_ESTABLISHED and signed -100.0 bps.
    4. Two pages rendered strictly without overflow.
    """
    pdf_path = str(tmp_path / "dark_terminal_report.pdf")

    summary = ForensicSummary(
        ticker="HINDUNILVR",
        company_name="Hindustan Unilever Ltd",
        quarters_analyzed=["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
        debtor_days={"Jun 2024": 16.0, "Sep 2024": 16.5, "Dec 2024": 17.0, "Mar 2025": 19.0},
        sales_growth_yoy={"Jun 2024": 4.1, "Sep 2024": 3.8, "Dec 2024": 4.5, "Mar 2025": 5.2},
        expense_adjusted_residual={"Jun 2024": -0.8, "Sep 2024": -1.2, "Dec 2024": -0.5, "Mar 2025": -1.5},
        beneish_dsri=1.188,
        debtor_days_ratio_proxy=1.188,
        operating_margin_delta_bps=-100.0,
        margin_wedge_bps=None,
        peer_spread_days=1.5,
        anomalies=[
            AnomalyCandidate(
                metric_name="Debtor Days Elongation",
                metric_type="debtor_days",
                unit="d",
                period="Mar 2025",
                target_value=19.0,
                baseline_value=16.0,
                delta=3.0,
                materiality=1.0,
                severity_score=48.0,
                description="Debtor days elongated from 16.0d to 19.0d (+3.0d YoY stretch).",
                timeline_trajectory="16.0d -> 19.0d",
                direction="adverse"
            ),
            AnomalyCandidate(
                metric_name="Operating Margin Compression & Expense Drag",
                metric_type="margin_compression",
                unit="bps",
                period="Mar 2025",
                target_value=23.0,
                baseline_value=24.0,
                delta=-100.0,
                materiality=0.8,
                severity_score=80.0,
                description="Operating margin compressed from 24.0% to 23.0% (-100.0 bps YoY).",
                direction="adverse"
            )
        ]
    )

    discovery = {
        "finding_heading": "Observed Fact (Causal Explanation Not Established)",
        "1_The_Discovery": "HUL expanded debtor days from 16d to 19d amid operating margin compression of -100.0 bps.",
        "2_Why_It_Matters": [
            "Trade credit terms relaxed across general trade channels.",
            "Operating margin contracted from 24.0% to 23.0% (-100.0 bps drag).",
            "Peer spread widened by +1.5 days against FMCG sector median."
        ],
        "3_Evidence": [
            "https://screener.in/company/HINDUNILVR/",
            "https://nsearchives.nseindia.com/corporate/HINDUNILVR_Results.pdf"
        ],
        "4_Timeline": "Trailing statutory quarters ending March 2025.",
        "5_Numbers": "Canonical DSRI: 1.188 | Debtor Days: +3.0d | Operating Margin Δ: -100.0 bps.",
        "6_Counterargument": "Seasonal distributor credit buffers and product category mix shifts.",
        "7_Falsification_Condition": "Disproven if debtor days compress below 16d for >=2 consecutive quarters.",
        "8_Evidence_Strength": "NOT_ESTABLISHED (Data Sufficiency: LIMITED): Evidence shows trade credit widening, but channel stuffing remains speculative."
    }

    generated_path = export_forensic_pdf(
        ticker="HINDUNILVR",
        company_name="Hindustan Unilever Ltd",
        summary_data=summary,
        discovery=discovery,
        output_path=pdf_path
    )

    assert Path(generated_path).exists()

    # Open with PyMuPDF
    doc = fitz.open(generated_path)
    assert len(doc) == 2, f"Report must be strictly 2 pages, got {len(doc)}"

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        # Zero tolerance for INCONCLUSIVE
        assert "INCONCLUSIVE" not in text.upper(), f"Found INCONCLUSIVE on page {page_num + 1}"

        # Render page to high-res pixmap (150 DPI)
        pix = page.get_pixmap(dpi=150)
        img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))

        # Check background color: sample corner pixels (10, 10), (10, width-10)
        # Background is #05070A -> R=5, G=7, B=10
        corner_pixels = [
            img_data[10, 10, :3],
            img_data[10, pix.width - 10, :3],
            img_data[pix.height - 10, 10, :3],
            img_data[pix.height - 10, pix.width - 10, :3],
        ]
        for p in corner_pixels:
            assert p[0] < 25 and p[1] < 25 and p[2] < 25, f"Expected dark background pixel, got {p}"

        # Verify page is not mostly white
        # Mean brightness should be low (< 60 out of 255)
        mean_brightness = np.mean(img_data[:, :, :3])
        assert mean_brightness < 60.0, f"Page {page_num + 1} appears too bright (mean={mean_brightness})"

    # Page 1 specific text asserts
    p1_text = doc[0].get_text()
    assert "HINDUSTAN UNILEVER LTD" in p1_text.upper()
    assert "-100.0 bps" in p1_text or "-100 bps" in p1_text

    # Page 2 specific text asserts
    p2_text = doc[1].get_text()
    assert "VERDICT: NOT ESTABLISHED" in p2_text
    assert "NOT_ESTABLISHED" in p2_text
    assert "LIMITED" in p2_text
    assert "Disproven if" in p2_text

    doc.close()
