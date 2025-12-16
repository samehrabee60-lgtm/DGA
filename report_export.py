
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from io import BytesIO
import datetime as dt, os

def generate_sample_pdf(row: dict):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFillColor(colors.HexColor("#1f4e79"))
    c.rect(0, h-2.8*cm, w, 2.8*cm, stroke=0, fill=1)
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, 1*cm, h-2.4*cm, width=2.2*cm, height=2.2*cm, preserveAspectRatio=True)
        except Exception:
            pass
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 16)
    c.drawString(4*cm, h-1.3*cm, "Transformer Oil DGA Report")
    c.setFont("Helvetica", 9); c.drawRightString(w-1.5*cm, h-1.1*cm, dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    y = h-3.5*cm; c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Asset & Sample Info"); y -= 0.5*cm; c.setFont("Helvetica", 10)
    def line(lbl, key):
        nonlocal y; c.drawString(2*cm, y, f"{lbl}: {row.get(key,'')}"); y -= 0.6*cm
    line("Substation (المحطة)", "المحطة"); line("Transformer (المحول)", "المحول"); line("Voltage (الجهد)", "الجهد")
    line("Sample Date (تاريخ العينة)", "تاريخ العينة"); line("Analysis Date (تاريخ التحليل)", "تاريخ التحليل"); line("Retest Date (تاريخ إعادة التحليل)", "تاريخ إعادة التحليل")
    y -= 0.2*cm; c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "DGA Results (ppm)"); y -= 0.6*cm; c.setFont("Helvetica", 10)
    gases = [("O2","O2"),("N2","N2"),("H2","H2"),("CO","CO"),("CO2","CO2"),("CH4","CH4"),("C2H6","C2H6"),("C2H4","C2H4"),("C2H2","C2H2"),("O2/N2","O2/N2")]
    x1, x2 = 2*cm, 10*cm
    for g_label, key in gases:
        c.drawString(x1, y, f"{g_label}:")
        c.drawString(x2, y, f"{row.get(key,'')}")
        y -= 0.5*cm
    y -= 0.2*cm; c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Analysis Summary"); y -= 0.6*cm; c.setFont("Helvetica", 10)
    c.drawString(2*cm, y, f"Result of analysis: {row.get('Result of analysis','')}"); y -= 0.5*cm
    c.drawString(2*cm, y, f"DGA: {row.get('DGA','')}"); y -= 0.5*cm
    c.drawString(2*cm, y, f"Recommended: {row.get('C.Recommended','')}"); y -= 0.7*cm
    c.setFont("Helvetica-Oblique", 9); c.setFillColor(colors.grey); c.drawString(2*cm, y, "Retest date = Analysis date + n months.");
    
    # Add AI Report section
    ai_text = str(row.get("AI Report",""))
    if ai_text and ai_text.lower() != "nan":
        y -= 1.0*cm
        # Check for page break
        if y < 4*cm:
            c.showPage(); y = h - 3*cm
            
        c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, y, "AI Diagnosis:")
        y -= 0.6*cm
        c.setFont("Helvetica", 10)
        
        # Simple wrapping
        from reportlab.lib.utils import simpleSplit
        lines = simpleSplit(ai_text, "Helvetica", 10, w-4*cm)
        for line in lines:
            if y < 2*cm:
                 c.showPage()
                 y = h - 2.5*cm
                 c.setFont("Helvetica", 10)
            c.drawString(2*cm, y, line)
            y -= 0.5*cm

    c.showPage(); c.save(); return buf.getvalue(), "Sample_Report.pdf"
