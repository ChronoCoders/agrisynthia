# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
REPORTS_DIR = MEDIA_ROOT / "reports"

COLOR_GREEN = colors.HexColor("#2E7D32")
COLOR_LIGHT_GREEN = colors.HexColor("#E8F5E9")
COLOR_GREY = colors.HexColor("#757575")
COLOR_DARK = colors.HexColor("#212121")
COLOR_WHITE = colors.white


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=22,
                                textColor=COLOR_GREEN, spaceAfter=6, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontSize=11,
                                   textColor=COLOR_GREY, spaceAfter=4, alignment=TA_CENTER),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontSize=13,
                                  textColor=COLOR_GREEN, spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10,
                               textColor=COLOR_DARK, leading=16),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8,
                                textColor=COLOR_GREY),
    }


def generate_detection_pdf(detection_result) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"detection_{detection_result.pk}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = REPORTS_DIR / filename

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = _styles()
    story = []

    story.append(Paragraph("FarmVision", styles["title"]))
    story.append(Paragraph("Meyve Tespit Raporu", styles["subtitle"]))
    story.append(Paragraph(f"Oluşturulma: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_GREEN, spaceAfter=12))

    story.append(Paragraph("Tespit Özeti", styles["section"]))

    fruit_names = {
        "mandalina": "Mandalina", "elma": "Elma", "armut": "Armut",
        "seftale": "Şeftali", "nar": "Nar",
    }

    summary_data = [
        ["Alan", "Değer"],
        ["Meyve Türü", fruit_names.get(detection_result.fruit_type, detection_result.fruit_type)],
        ["Tespit Edilen Meyve", f"{detection_result.detected_count:,} adet"],
        ["Ağaç Sayısı", f"{detection_result.tree_count:,} adet"],
        ["Ağaç Yaşı", f"{detection_result.tree_age} yıl"],
        ["Tek Ağaç Ağırlığı", f"{detection_result.weight:.2f} kg"],
        ["Toplam Ağırlık (Tahmini)", f"{detection_result.total_weight:.2f} kg"],
        ["Güven Skoru", f"{detection_result.confidence_score:.1%}" if detection_result.confidence_score else "—"],
        ["Model Versiyonu", detection_result.model_version or "—"],
        ["İşlem Süresi", f"{detection_result.processing_time:.2f} sn"],
        ["Tespit Tarihi", detection_result.created_at.strftime("%d.%m.%Y %H:%M")],
    ]

    # Convert table data to Paragraphs where needed to handle potential encoding issues or long text
    # But here simple strings are mostly fine.
    
    table = Table(summary_data, colWidths=[6*cm, 10*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_WHITE, COLOR_LIGHT_GREEN]),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWHEIGHT", (0, 0), (-1, -1), 22),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    story.append(table)

    story.append(Paragraph("Tespit Görüntüsü", styles["section"]))
    # Ensure image_path is relative to MEDIA_ROOT correctly
    # detection_result.image_path is usually stored relative to MEDIA_ROOT in Django
    img_path = MEDIA_ROOT / str(detection_result.image_path)
    if img_path.exists():
        try:
            # Adjust width/height while keeping aspect ratio is handled by 'proportional' kind?
            # ReportLab Image kind='proportional' isn't standard in basic Image class AFAIK, 
            # but let's stick to the prompt's code. If it fails, I might need to adjust.
            # Actually standard ReportLab Image doesn't have 'kind'. 
            # However, I must follow the prompt exactly. 
            # Wait, if the prompt code has `kind="proportional"`, maybe they use a custom Image class or newer version?
            # I will write exactly what is in the prompt.
            img = Image(str(img_path), width=12*cm, height=9*cm, kind="proportional")
            story.append(img)
        except Exception as e:
            logger.warning("Detection image could not be embedded: %s", e)
            story.append(Paragraph("(Görüntü yüklenemedi)", styles["body"]))
    else:
        story.append(Paragraph("(Görüntü dosyası bulunamadı)", styles["body"]))

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_GREY))
    story.append(Paragraph(
        "Bu rapor FarmVision AI Sistemi tarafından otomatik olarak oluşturulmuştur.",
        styles["small"]
    ))

    doc.build(story)
    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    logger.info("Detection PDF generated: %s", output_path)
    # Return relative path for storage in FileField/CharField
    return f"reports/{filename}"
