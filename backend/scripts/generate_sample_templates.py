"""
One-time authoring script that produces the two placeholder .docx templates
referenced by corpus/templates/manifest.json. Each {{ field }} placeholder is
written as a single run so docxtpl (Jinja2-over-docx) can substitute it
cleanly at render time.

Run once from the backend/ directory:
    python scripts/generate_sample_templates.py

Real templates supplied later should follow the same convention: plain
paragraphs with `{{ field_key }}` placeholders matching manifest.json.
"""
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

_OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus", "templates")


def _title(doc, text):
    p = doc.add_heading(text, level=0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def build_bail_application():
    doc = Document()
    _title(doc, "APPLICATION FOR BAIL")

    doc.add_paragraph("IN THE {{ court_name }}")
    doc.add_paragraph("Case No.: {{ case_no }}    FIR No.: {{ fir_no }}")
    doc.add_paragraph("Police Station: {{ police_station }}")
    doc.add_paragraph("Sections Charged: {{ sections_charged }}")
    doc.add_paragraph()

    doc.add_paragraph("BETWEEN:")
    doc.add_paragraph("{{ applicant_name }}, residing at {{ applicant_address }} ... Applicant")
    doc.add_paragraph("AND")
    doc.add_paragraph("{{ filed_against }} ... Respondent")
    doc.add_paragraph()

    doc.add_heading("APPLICATION UNDER SECTION 439 CrPC FOR GRANT OF BAIL", level=1)
    doc.add_paragraph(
        "The Applicant above named respectfully submits as follows:"
    )
    doc.add_paragraph("1. That the Applicant was arrested on {{ date_of_arrest }} in connection with the above case.")
    doc.add_paragraph("2. Grounds for bail:")
    doc.add_paragraph("{{ grounds_for_bail }}")
    doc.add_paragraph(
        "3. That the Applicant undertakes to abide by all conditions the Hon'ble Court may impose "
        "and shall not tamper with evidence or influence witnesses."
    )
    doc.add_paragraph(
        "PRAYER: It is therefore most respectfully prayed that this Hon'ble Court may be pleased to "
        "release the Applicant on bail in the interest of justice."
    )
    doc.add_paragraph()

    doc.add_paragraph("Place: {{ filing_place }}")
    doc.add_paragraph("Date: {{ filing_date }}")
    doc.add_paragraph()
    sig = doc.add_paragraph("_________________________")
    sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    lbl = doc.add_paragraph("(Applicant / Counsel for Applicant)")
    lbl.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.save(os.path.join(_OUT_DIR, "bail_application.docx"))


def build_affidavit():
    doc = Document()
    _title(doc, "AFFIDAVIT")

    doc.add_paragraph(
        "I, {{ deponent_name }}, {{ deponent_relation }}, aged about {{ deponent_age }} years, "
        "residing at {{ deponent_address }}, do hereby solemnly affirm and state as follows:"
    )
    doc.add_paragraph()
    doc.add_paragraph("{{ statement_content }}")
    doc.add_paragraph()
    doc.add_paragraph(
        "I state that the contents of this affidavit are true and correct to the best of my "
        "knowledge and belief, and nothing material has been concealed therefrom."
    )
    doc.add_paragraph()

    doc.add_paragraph("Place: {{ place }}")
    doc.add_paragraph("Date: {{ date }}")
    doc.add_paragraph()
    sig = doc.add_paragraph("_________________________")
    sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    lbl = doc.add_paragraph("(Deponent)")
    lbl.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.save(os.path.join(_OUT_DIR, "affidavit.docx"))


if __name__ == "__main__":
    os.makedirs(_OUT_DIR, exist_ok=True)
    build_bail_application()
    build_affidavit()
    print(f"Wrote bail_application.docx and affidavit.docx to {_OUT_DIR}")
