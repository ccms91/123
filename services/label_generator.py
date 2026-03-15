"""
Label PDF Generator
Generates 8 labels (80mm x 45mm each) on a single A4 page.
Layout: 2 columns x 4 rows.
"""

import io
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# ── Label dimensions ───────────────────────────────────────────────────────
LABEL_W = 80 * mm
LABEL_H = 45 * mm
MARGIN_LEFT = 15 * mm
MARGIN_TOP = 20 * mm
COL_GAP = 10 * mm
ROW_GAP = 5 * mm


def _make_qr(data_str, box_size=6):
    """Generate a QR code and return it as a ReportLab-compatible ImageReader."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=1,
    )
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    # Convert PIL image to bytes for ReportLab
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _label_position(index):
    """Return (x, y) for the bottom-left corner of label at given index (0-7).
    Labels are laid out left-to-right, top-to-bottom on A4.
    Index 0 = top-left, 1 = top-right, 2 = second-row-left, etc.
    """
    page_w, page_h = A4
    col = index % 2
    row = index // 2
    x = MARGIN_LEFT + col * (LABEL_W + COL_GAP)
    y = page_h - MARGIN_TOP - (row + 1) * LABEL_H - row * ROW_GAP
    return x, y


def _draw_label_border(c, x, y):
    """Draw a dashed border around the label for cutting guide."""
    c.saveState()
    c.setDash(2, 2)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.rect(x, y, LABEL_W, LABEL_H, stroke=1, fill=0)
    c.restoreState()


def _draw_qr_left(c, x, y, qr_img, size=35*mm):
    """Draw QR code on the left half of the label."""
    qr_x = x + 3 * mm
    qr_y = y + (LABEL_H - size) / 2
    c.drawImage(qr_img, qr_x, qr_y, width=size, height=size)


def _draw_label_1(c, x, y, data, qr_img):
    """Label 1: QR (name+passport) left | 'Urine' right"""
    _draw_label_border(c, x, y)
    _draw_qr_left(c, x, y, qr_img)

    # Right half
    rx = x + LABEL_W / 2 + 2 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(rx, y + LABEL_H - 18 * mm, "Urine")


def _draw_label_2(c, x, y, data, qr_img):
    """Label 2: QR left | 'Height & Weight' right with blanks"""
    _draw_label_border(c, x, y)
    _draw_qr_left(c, x, y, qr_img)

    rx = x + LABEL_W / 2 + 2 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(rx, y + LABEL_H - 12 * mm, "Height & Weight")

    c.setFont("Helvetica", 11)
    c.drawString(rx, y + LABEL_H - 22 * mm, "Height: ________ cm")
    c.drawString(rx, y + LABEL_H - 32 * mm, "Weight: ________ kg")


def _draw_label_3(c, x, y, data, qr_img):
    """Label 3: QR left | 'BP' right"""
    _draw_label_border(c, x, y)
    _draw_qr_left(c, x, y, qr_img)

    rx = x + LABEL_W / 2 + 2 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(rx, y + LABEL_H - 18 * mm, "BP")


def _draw_label_4(c, x, y, data, qr_img):
    """Label 4: QR left | 'Tag to patient' right"""
    _draw_label_border(c, x, y)
    _draw_qr_left(c, x, y, qr_img)

    rx = x + LABEL_W / 2 + 2 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(rx, y + LABEL_H - 18 * mm, "Tag to Patient")


def _draw_label_5_6(c, x, y, data):
    """Labels 5 & 6: Blood tube label with patient info (no QR).
    Contains: Name, DOB, Gender, Nationality, Clinic HCI, Dr MCR
    """
    _draw_label_border(c, x, y)

    lx = x + 3 * mm
    top = y + LABEL_H - 8 * mm
    line_h = 6.5 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(lx, top, f"Name: {data['name']}")
    c.drawString(lx, top - line_h, f"DOB: {data['dob_display']}")
    c.drawString(lx, top - 2 * line_h, f"Gender: {data['sex']}")
    c.drawString(lx, top - 3 * line_h, f"Nationality: {data['nationality']}")
    c.drawString(lx, top - 4 * line_h, f"HCI: {data.get('clinic_hci', '')}")
    c.drawString(lx, top - 5 * line_h, f"Dr MCR: {data.get('doctor_mcr', '')}")


def _draw_label_7(c, x, y, data):
    """Label 7: QR code for lab order form.
    Format: Passport|MCR|Name|DDMMYYYY|Gender|Nationality|HCI||Test
    """
    _draw_label_border(c, x, y)

    # Build QR data string
    dob_formatted = data["dob_ddmmyyyy"]
    qr_data = (
        f"{data['passport_number']}|"
        f"{data.get('doctor_mcr', '')}|"
        f"{data['name']}|"
        f"{dob_formatted}|"
        f"{data['sex']}|"
        f"{data['nationality']}|"
        f"{data.get('clinic_hci', '')}||"
        f"{data.get('test_to_order', '')}"
    )

    qr_img = _make_qr(qr_data)

    # Draw QR centered and larger since this is the main content
    qr_size = 38 * mm
    qr_x = x + (LABEL_W - qr_size) / 2
    qr_y = y + 2 * mm
    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)

    # Small text above QR
    c.setFont("Helvetica", 6)
    c.drawCentredString(x + LABEL_W / 2, y + LABEL_H - 5 * mm, "Lab Order QR")


def _draw_label_8(c, x, y, data):
    """Label 8: Left = patient name + passport | Right = 'CXR'"""
    _draw_label_border(c, x, y)

    # Left half: patient info
    lx = x + 3 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(lx, y + LABEL_H - 14 * mm, data["name"])
    c.setFont("Helvetica", 10)
    c.drawString(lx, y + LABEL_H - 24 * mm, data["passport_number"])

    # Right half: CXR
    rx = x + LABEL_W / 2 + 5 * mm
    c.setFont("Helvetica-Bold", 20)
    c.drawString(rx, y + LABEL_H - 22 * mm, "CXR")


def generate_labels_pdf(data):
    """
    Generate a PDF with 8 labels on a single A4 page.
    Returns PDF as bytes.

    data dict must contain:
        name, passport_number, sex, dob (YYYY-MM-DD), nationality,
        clinic_hci, doctor_mcr, test_to_order
    """
    # Pre-process DOB formats
    # Input is YYYY-MM-DD from HTML date input
    dob_parts = data["dob"].split("-")  # ['YYYY', 'MM', 'DD']
    data["dob_display"] = f"{dob_parts[2]}/{dob_parts[1]}/{dob_parts[0]}"  # DD/MM/YYYY
    data["dob_ddmmyyyy"] = f"{dob_parts[2]}{dob_parts[1]}{dob_parts[0]}"  # DDMMYYYY

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Patient Labels")

    # Generate the patient QR code (name + passport) used by labels 1-4
    patient_qr_data = f"{data['name']}|{data['passport_number']}"
    patient_qr_img = _make_qr(patient_qr_data)

    # Draw all 8 labels
    label_funcs = [
        lambda c, x, y: _draw_label_1(c, x, y, data, patient_qr_img),
        lambda c, x, y: _draw_label_2(c, x, y, data, patient_qr_img),
        lambda c, x, y: _draw_label_3(c, x, y, data, patient_qr_img),
        lambda c, x, y: _draw_label_4(c, x, y, data, patient_qr_img),
        lambda c, x, y: _draw_label_5_6(c, x, y, data),  # Label 5
        lambda c, x, y: _draw_label_5_6(c, x, y, data),  # Label 6 (same as 5)
        lambda c, x, y: _draw_label_7(c, x, y, data),
        lambda c, x, y: _draw_label_8(c, x, y, data),
    ]

    for i, draw_fn in enumerate(label_funcs):
        x, y = _label_position(i)
        draw_fn(c, x, y)

    c.save()
    return buf.getvalue()
