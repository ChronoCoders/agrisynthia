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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
REPORTS_DIR = MEDIA_ROOT / "reports"

COLOR_GREEN = colors.HexColor("#2E7D32")
COLOR_LIGHT_GREEN = colors.HexColor("#E8F5E9")
COLOR_BLUE = colors.HexColor("#1565C0")
COLOR_ORANGE = colors.HexColor("#E65100")
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
                                  textColor=COLOR_BLUE, spaceBefore=14, spaceAfter=6),
        "subsection": ParagraphStyle("subsection", parent=base["Heading3"], fontSize=11,
                                     textColor=COLOR_GREEN, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10,
                               textColor=COLOR_DARK, leading=16),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8,
                                textColor=COLOR_GREY),
        "caption": ParagraphStyle("caption", parent=base["Normal"], fontSize=9,
                                  textColor=COLOR_GREY, alignment=TA_CENTER, spaceBefore=4, spaceAfter=10),
    }

def _get_image_flowable(path_str, width=16*cm, height=10*cm):
    if not path_str:
        return Paragraph("(Görüntü yolu belirtilmemiş)", _styles()["body"])
    
    img_path = MEDIA_ROOT / path_str
    if img_path.exists():
        try:
            return Image(str(img_path), width=width, height=height, kind="proportional")
        except Exception as e:
            logger.warning("Image could not be embedded: %s", e)
            return Paragraph("(Görüntü yüklenemedi)", _styles()["body"])
    else:
        return Paragraph("(Görüntü dosyası bulunamadı)", _styles()["body"])

def generate_drone_pdf(project, analysis_data: dict) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"drone_{project.pk}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = REPORTS_DIR / filename

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = _styles()
    story = []

    # Title Section
    story.append(Paragraph("FarmVision — Drone Analiz Raporu", styles["title"]))
    story.append(Paragraph(f"Oluşturulma: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_GREEN, spaceAfter=12))

    # Project Info Table
    story.append(Paragraph("Proje Bilgileri", styles["section"]))
    
    project_data = [
        ["Alan", "Değer"],
        ["Proje Adı", project.name],
        ["Çiftlik", project.farm_name or "—"],
        ["Tarla", project.field_name or "—"],
        ["Durum", project.get_status_display()],
        ["Analiz Algoritması", analysis_data.get('algorithm', 'Bilinmiyor').upper()],
        ["Analiz Tarihi", analysis_data.get('analysis_date', '—')],
    ]

    table = Table(project_data, colWidths=[6*cm, 10*cm])
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
    
    story.append(PageBreak())

    # Orthophoto
    story.append(Paragraph("Ortofoto Görüntüsü", styles["section"]))
    story.append(_get_image_flowable(analysis_data.get('ortophoto_thumbnail_path')))
    story.append(Paragraph("Şekil 1: Proje sahasının ortofoto görüntüsü", styles["caption"]))

    story.append(Spacer(1, 1*cm))

    # Vegetation Index Map
    story.append(Paragraph("Vejetasyon İndeks Haritası", styles["section"]))
    story.append(_get_image_flowable(analysis_data.get('ndvi_map_path')))
    story.append(Paragraph(f"Şekil 2: {analysis_data.get('algorithm', 'NDVI').upper()} Analiz Haritası", styles["caption"]))

    # Vegetation Stats Table
    veg_stats = analysis_data.get('vegetation_stats', {})
    if veg_stats:
        story.append(Paragraph("Vejetasyon İstatistikleri", styles["subsection"]))
        stats_data = [["Metrik", "Değer"]] + [[k, f"{v:.4f}" if isinstance(v, float) else str(v)] for k, v in veg_stats.items()]
        
        t_stats = Table(stats_data, colWidths=[8*cm, 8*cm])
        t_stats.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_GREY),
            ("ROWHEIGHT", (0, 0), (-1, -1), 20),
        ]))
        story.append(t_stats)

    story.append(PageBreak())

    # Stress Zone Map
    story.append(Paragraph("Stres Zonu Haritası", styles["section"]))
    story.append(_get_image_flowable(analysis_data.get('stress_zone_map_path')))
    story.append(Paragraph("Şekil 3: Tespit edilen stres bölgeleri", styles["caption"]))

    # Stress Zones Table
    stress_zones = analysis_data.get('stress_zones', [])
    if stress_zones:
        story.append(Paragraph("Stres Zonu Detayları", styles["subsection"]))
        zone_data = [["Zone ID", "Stres Sınıfı", "Alan (ha)"]]
        for zone in stress_zones:
            zone_data.append([
                str(zone.get('zone_id', '-')),
                str(zone.get('stress_class', '-')),
                f"{zone.get('area_ha', 0):.4f}"
            ])
            
        t_zones = Table(zone_data, colWidths=[4*cm, 6*cm, 4*cm])
        t_zones.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_ORANGE),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_GREY),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ]))
        story.append(t_zones)

    story.append(Spacer(1, 0.5*cm))

    # Yield Prediction
    yield_pred = analysis_data.get('yield_prediction', {})
    if yield_pred:
        story.append(Paragraph("Verim Tahmini", styles["section"]))
        yield_data = [["Metrik", "Tahmin"]] + [[k, str(v)] for k, v in yield_pred.items()]
        
        t_yield = Table(yield_data, colWidths=[8*cm, 8*cm])
        t_yield.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_GREY),
        ]))
        story.append(t_yield)

    story.append(Spacer(1, 0.5*cm))

    # Recommendations
    recommendations = analysis_data.get('recommendations', [])
    if recommendations:
        story.append(Paragraph("Öneriler ve Aksiyon Planı", styles["section"]))
        rec_data = [["Önem Derecesi", "Aksiyon"]]
        
        # Color coding for severity
        row_colors = []
        for rec in recommendations:
            severity = rec.get('severity', '').lower()
            action = rec.get('action', '')
            rec_data.append([severity.upper(), action])
            
            if severity == 'kritik':
                row_colors.append(colors.red)
            elif severity == 'yüksek':
                row_colors.append(colors.orange)
            elif severity == 'orta':
                row_colors.append(colors.yellow)
            else:
                row_colors.append(colors.white)

        t_rec = Table(rec_data, colWidths=[4*cm, 12*cm])
        ts = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_GREY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        
        # Apply row background colors based on severity
        # Note: ReportLab TableStyle applies to ranges. 
        # We need to iterate and apply background color for the first column of each row
        for i, color in enumerate(row_colors):
            row_idx = i + 1
            if color != colors.white:
                 ts.append(("BACKGROUND", (0, row_idx), (0, row_idx), color))
                 if color == colors.red:
                     ts.append(("TEXTCOLOR", (0, row_idx), (0, row_idx), colors.white))
            
        t_rec.setStyle(TableStyle(ts))
        story.append(t_rec)

    # Footer
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_GREY))
    story.append(Paragraph(
        "Bu rapor FarmVision AI Sistemi tarafından otomatik olarak oluşturulmuştur.",
        styles["small"]
    ))

    doc.build(story)
    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    logger.info("Drone PDF generated: %s", output_path)
    return f"reports/{filename}"
