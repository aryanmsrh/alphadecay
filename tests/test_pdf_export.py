import os
import pytest
from pathlib import Path
import pypdf
from engine.models import ForensicSummary, AnomalyCandidate
from exporter.pdf_report import export_forensic_pdf

def test_pdf_report_generation_and_page_layout(tmp_path):
    output_pdf = str(tmp_path / "test_report.pdf")
    
    summary = ForensicSummary(
        ticker="NESTLEIND",
        company_name="Nestle India Ltd",
        quarters_analyzed=["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
        debtor_days={"Jun 2024": 15.0, "Sep 2024": 16.0, "Dec 2024": 15.0, "Mar 2025": 18.0},
        sales_growth_yoy={"Jun 2024": None, "Sep 2024": None, "Dec 2024": 8.5, "Mar 2025": 9.2},
        expense_adjusted_residual={"Jun 2024": None, "Sep 2024": None, "Dec 2024": 2.1, "Mar 2025": 1.8},
        beneish_dsri=1.045,
        debtor_days_ratio_proxy=1.200,
        beneish_sgi=1.092,
        beneish_gmi=1.02,
        beneish_aqi=1.0,
        margin_wedge_bps=80.0,
        distribution_drag_bps=95.0,
        peer_spread_days=1.5,
        anomalies=[
            AnomalyCandidate(
                metric_name="Debtor Days Elongation",
                metric_type="debtor_days",
                unit="d",
                period="Mar 2025",
                target_value=18.0,
                baseline_value=15.0,
                delta=3.0,
                materiality=1.0,
                severity_score=36.0,
                description="Debtor days shifted from 15.0d to 18.0d.",
                timeline_trajectory="15d -> 18d"
            )
        ]
    )

    discovery = {
        "1_The_Discovery": "Nestle India exhibited a 3-day debtor stretch while gross margins compressed by 80 bps.",
        "2_Why_It_Matters": [
            "Quick commerce listing fees and distributor inventory push absorbed working capital.",
            "Operating cash flow conversion slowed to 68% of operating profit.",
            "Competitor peer spread widened by +1.5 days."
        ],
        "3_Evidence": ["https://screener.in/company/NESTLEIND/consolidated/"],
        "4_Timeline": "Trailing statutory quarters ending March 2025.",
        "5_Numbers": "Canonical DSRI: 1.045 | Debtor Days: 18d vs 15d | Margin Wedge: +80 bps.",
        "6_Counterargument": "Input raw material inflation in cocoa and coffee prompted strategic distributor credit buffers.",
        "7_Falsification_Condition": "Disproven if debtor days compress below 15d for >=2 consecutive quarters.",
        "8_Evidence_Strength": "NOT_ESTABLISHED (Data Sufficiency: LIMITED): Channel adjustments explain part of the divergence alongside commodity cost pressures."
    }

    generated_path = export_forensic_pdf(
        ticker="NESTLEIND",
        company_name="Nestle India Ltd",
        summary_data=summary,
        discovery=discovery,
        output_path=output_pdf
    )

    assert Path(generated_path).exists()
    reader = pypdf.PdfReader(generated_path)
    # Must be strictly 2 pages
    assert len(reader.pages) == 2

    # Check text content of pages
    page1_text = reader.pages[0].extract_text()
    page2_text = reader.pages[1].extract_text()
    combined_text = page1_text + "\n" + page2_text

    assert "NESTLE INDIA LTD" in combined_text.upper()
    assert "DSRI" in combined_text
    assert "Expense Residual" in combined_text
    assert "NOT_ESTABLISHED" in combined_text
    assert "INCONCLUSIVE" not in combined_text

def test_forensic_chart_generation(tmp_path):
    from exporter.forensic_chart import generate_forensic_chart
    output_png = str(tmp_path / "custom_chart.png")

    summary = ForensicSummary(
        ticker="BRITANNIA",
        company_name="Britannia Industries Ltd",
        quarters_analyzed=["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
        debtor_days={"Jun 2024": 12.0, "Sep 2024": 13.5, "Dec 2024": None, "Mar 2025": 16.0},
        sales_growth_yoy={"Jun 2024": 5.0, "Sep 2024": 6.2, "Dec 2024": 7.1, "Mar 2025": 4.5},
        expense_adjusted_residual={"Jun 2024": -1.2, "Sep 2024": 0.5, "Dec 2024": 1.1, "Mar 2025": -0.8},
        anomalies=[]
    )

    chart_path = generate_forensic_chart(summary, output_path=output_png)
    assert Path(chart_path).exists()
    assert Path(chart_path).stat().st_size > 1000

def test_pdf_report_no_material_anomaly(tmp_path):
    output_pdf = str(tmp_path / "clean_report.pdf")

    summary = ForensicSummary(
        ticker="HINDUNILVR",
        company_name="Hindustan Unilever Ltd",
        quarters_analyzed=["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
        debtor_days={"Jun 2024": 16.0, "Sep 2024": 16.5, "Dec 2024": 17.0, "Mar 2025": 17.0},
        sales_growth_yoy={"Jun 2024": 4.0, "Sep 2024": 4.5, "Dec 2024": 5.0, "Mar 2025": 4.8},
        expense_adjusted_residual={"Jun 2024": 0.2, "Sep 2024": 0.1, "Dec 2024": 0.3, "Mar 2025": 0.1},
        no_material_anomaly_detected=True,
        sector="Fast-Moving Consumer Goods",
        as_of_date="2025-03-31",
        anomalies=[]
    )

    discovery = {
        "1_The_Discovery": "No material forensic divergence detected across trailing statutory reporting periods.",
        "2_Why_It_Matters": [
            "Financial statements conform to baseline sector bounds.",
            "Working capital velocity and revenue recognition reflect normal seasonal variances."
        ],
        "3_Evidence": ["https://screener.in/company/HINDUNILVR/consolidated/"],
        "4_Timeline": "Trailing statutory quarters ending March 2025.",
        "5_Numbers": "All Beneish and working capital indicators within normal baseline limits.",
        "6_Counterargument": "No forensic dispute detected.",
        "7_Falsification_Condition": "Material divergence emerges in future statutory filings.",
        "8_Evidence_Strength": "NO MATERIAL FORENSIC ANOMALY DETECTED"
    }

    generated_path = export_forensic_pdf(
        ticker="HINDUNILVR",
        company_name="Hindustan Unilever Ltd",
        summary_data=summary,
        discovery=discovery,
        output_path=output_pdf
    )

    assert Path(generated_path).exists()
    reader = pypdf.PdfReader(generated_path)
    assert len(reader.pages) == 2

    combined_text = reader.pages[0].extract_text() + "\n" + reader.pages[1].extract_text()
    assert "HINDUSTAN UNILEVER LTD" in combined_text.upper()
    assert "Fast-Moving Consumer Goods" in combined_text
    assert "2025-03-31" in combined_text
    assert "NO MATERIAL FORENSIC ANOMALY DETECTED" in combined_text

