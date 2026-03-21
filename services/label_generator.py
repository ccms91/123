"""Generate an 8-up patient label PDF (Avery L7165 / 99.1 mm × 67.7 mm)."""

import io
import os
import subprocess
import sys
from datetime import datetime

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas

# ---------------------------------------------------------------------------
# Layout constants  (Avery L7165 – 2 cols × 4 rows on A4)
# ---------------------------------------------------------------------------
LABEL_W = 99.1 * mm
LABEL_H = 67.7 * mm
LEFT_MARGIN = 7.0 * mm
TOP_MARGIN = 13.5 * mm
COL_GAP = 2.6 * mm   # horizontal gap between the two columns
COLS = 2
ROWS = 4


def _make_qr_image(data: dict) -> io.BytesIO:
    payload = "\n".join(
        [
            f"Name:{data.get('name', '')}",
            f"Passport:{data.get('passport_number', '')}",
            f"DOB:{data.get('dob', '')}",
            f"Date:{data.get('visit_date', datetime.now().strftime('%d/%m/%Y'))}",
        ]
    )
    qr_img = qrcode.make(payload)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_label(
    c: pdf_canvas.Canvas,
    x: float,
    y: float,
    data: dict,
    qr_buf: io.BytesIO,
) -> None:
    pad = 2.5 * mm

    # Border
    c.setStrokeColor(colors.HexColor("#cccccc"))
    c.setLineWidth(0.4)
    c.rect(x, y, LABEL_W, LABEL_H)

    # QR code – left side
    qr_size = 22 * mm
    qr_x = x + pad
    qr_y = y + (LABEL_H - qr_size) / 2
    c.drawImage(
        qr_buf, qr_x, qr_y, width=qr_size, height=qr_size, preserveAspectRatio=True
    )
    qr_buf.seek(0)

    # Text – right of QR
    tx = x + pad + qr_size + pad
    ty = y + LABEL_H - pad

    # Clinic name header
    clinic = os.environ.get("CLINIC_NAME", "Health Screening Clinic")
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(colors.HexColor("#1a6bb0"))
    c.drawString(tx, ty - 8, clinic)

    # Divider line
    c.setStrokeColor(colors.HexColor("#1a6bb0"))
    c.setLineWidth(0.5)
    line_y = ty - 11
    c.line(tx, line_y, x + LABEL_W - pad, line_y)

    c.setFillColor(colors.black)

    # Patient name (bold, larger)
    c.setFont("Helvetica-Bold", 9)
    name = data.get("name", "")
    if len(name) > 30:
        name = name[:29] + "…"
    c.drawString(tx, line_y - 10, name)

    # Detail lines
    c.setFont("Helvetica", 7.5)
    lines = [
        f"DOB: {data.get('dob', '')}    {data.get('gender', '')}",
        f"Passport: {data.get('passport_number', '')}    {data.get('nationality', '')}",
        f"Corp: {data.get('corporation', '')[:28]}",
        f"Tests: {data.get('tests_required', '')[:28]}",
    ]
    ly = line_y - 22
    for line in lines:
        c.drawString(tx, ly, line)
        ly -= 9

    # Footer: date + doctor
    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColor(colors.HexColor("#555555"))
    visit_date = data.get("visit_date", datetime.now().strftime("%d/%m/%Y"))
    doctor = data.get("doctor_name", "")
    mcr = data.get("doctor_mcr", "")
    c.drawString(
        x + pad,
        y + pad,
        f"{visit_date}    Dr {doctor}  {mcr}",
    )


def generate_labels(patient_data: dict, output_path: str) -> str:
    """Create a PDF with 8 identical patient labels and save to output_path."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    qr_buf = _make_qr_image(patient_data)
    page_w, page_h = A4

    c = pdf_canvas.Canvas(output_path, pagesize=A4)

    for row in range(ROWS):
        for col in range(COLS):
            x = LEFT_MARGIN + col * (LABEL_W + COL_GAP)
            y = page_h - TOP_MARGIN - (row + 1) * LABEL_H
            _draw_label(c, x, y, patient_data, qr_buf)

    c.save()
    return output_path


def print_labels(pdf_path: str) -> bool:
    """Send the label PDF to the default system printer. Returns True on success."""
    abs_path = os.path.abspath(pdf_path)
    try:
        if sys.platform == "win32":
            os.startfile(abs_path, "print")
        elif sys.platform == "darwin":
            subprocess.run(["lp", abs_path], check=True)
        else:
            subprocess.run(["lp", abs_path], check=True)
        return True
    except Exception as exc:
        print(f"[label_generator] Print error: {exc}", file=sys.stderr)
        return False
