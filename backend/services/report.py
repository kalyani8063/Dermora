from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import cv2
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

REPORT_VERSION = "Dermora Clinical Reference Template v1.0"
ANALYSIS_TYPE = "Full Facial Skin Assessment + Health Context"
PAGE_SIZE = landscape(A4)
ROOT_DIR = Path(__file__).resolve().parents[2]
LOGO_PATH = ROOT_DIR / "frontend" / "images" / "logo.png"

PRIMARY = colors.HexColor("#D85C92")
PRIMARY_DARK = colors.HexColor("#B33F72")
PRIMARY_SOFT = colors.HexColor("#F9E7EE")
TEXT = colors.HexColor("#18121B")
TEXT_SOFT = colors.HexColor("#655C69")
BORDER = colors.HexColor("#E8D7E0")
WHITE = colors.white


STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name="ReportTitle", parent=STYLES["Title"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=TEXT, spaceAfter=8))
STYLES.add(ParagraphStyle(name="SectionTitle", parent=STYLES["Heading2"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=TEXT, spaceAfter=8))
STYLES.add(ParagraphStyle(name="Intro", parent=STYLES["BodyText"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=TEXT_SOFT, spaceAfter=12))
STYLES.add(ParagraphStyle(name="BodySmall", parent=STYLES["BodyText"], fontName="Helvetica", fontSize=10, leading=13, textColor=TEXT_SOFT))
STYLES.add(ParagraphStyle(name="Label", parent=STYLES["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=PRIMARY_DARK, spaceAfter=3))
STYLES.add(ParagraphStyle(name="Value", parent=STYLES["BodyText"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=TEXT, spaceAfter=6))
STYLES.add(ParagraphStyle(name="Tiny", parent=STYLES["BodyText"], fontName="Helvetica", fontSize=9, leading=12, textColor=TEXT_SOFT))
STYLES.add(ParagraphStyle(name="CoverTitle", parent=STYLES["Title"], fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=WHITE, alignment=1, spaceAfter=8))
STYLES.add(ParagraphStyle(name="CoverBody", parent=STYLES["BodyText"], fontName="Helvetica", fontSize=11, leading=14, textColor=WHITE, alignment=1))


def generate_report(data):
    summary = (
        f"Skin score is {data['score']} with {data['acne_count']} visible acne spots, "
        f"{data['severity'].lower()} severity, and {data['pigmentation_coverage']}% pigmentation coverage."
    )
    key_insights = [
        f"Highest activity appears around the {data['top_zone'].replace('_', ' ')}.",
        f"Confidence score is {data['confidence']}% for this screen-level analysis.",
    ]
    recommendations = ["Keep tracking symptoms consistently to improve future trend accuracy."]
    return {"summary": summary, "key_insights": key_insights, "recommendations": recommendations}


def build_downloadable_report(output_dir: Path, analysis: dict, user_profile: dict, recent_logs: list[dict], previous_analysis: dict | None, original_image_path: Path, processed_image_path: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_id = uuid.uuid4().hex
    session_id = _build_session_id(analysis.get("analysis_date", ""), report_id)
    filename = f"Dermora_Report_{session_id}.pdf"
    report_path = output_dir / filename

    payload = {
        "analysis": analysis,
        "user": user_profile,
        "logs": recent_logs,
        "previous": previous_analysis or {},
        "quality": _evaluate_image_quality(original_image_path, analysis.get("confidence", 0)),
        "lesion_mix": _estimate_lesion_mix(analysis.get("acne", {}).get("count", 0), analysis.get("acne", {}).get("severity", "")),
        "health": _build_health_snapshot(recent_logs, user_profile),
        "session_id": session_id,
        "report_date": _format_datetime(analysis.get("analysis_date", "")),
    }

    doc = SimpleDocTemplate(str(report_path), pagesize=PAGE_SIZE, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=16 * mm)
    story = []
    story.extend(_cover_page(payload))
    story.extend(_image_quality_page(payload))
    story.extend(_summary_page(payload))
    story.extend(_acne_page(payload))
    story.extend(_zone_page(payload))
    story.extend(_pigmentation_page(payload))
    story.extend(_visual_page(original_image_path, processed_image_path))
    story.extend(_insights_page(payload))
    story.extend(_recommendations_page(payload))
    story.extend(_limitations_page(payload))
    doc.build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)

    return {"report_id": report_id, "session_id": session_id, "filename": filename, "path": str(report_path)}


def _build_session_id(analysis_date: str, report_id: str) -> str:
    try:
        stamp = datetime.fromisoformat(analysis_date.replace("Z", "+00:00")).strftime("%Y%m%d")
    except ValueError:
        stamp = datetime.now().strftime("%Y%m%d")
    return f"SKN-{stamp}-{report_id[:6].upper()}"


def _format_datetime(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%B %d, %Y - %I:%M %p UTC")
    except ValueError:
        return value or "Not available"


def _average_numeric(logs: list[dict], key: str):
    values = [log.get(key) for log in logs if isinstance(log.get(key), (int, float))]
    return (sum(values) / len(values)) if values else None


def _latest_non_empty(logs: list[dict], key: str) -> str:
    for log in logs:
        value = log.get(key)
        if value not in (None, "", []):
            return str(value)
    return ""


def _collect_list_values(logs: list[dict], key: str) -> list[str]:
    values = []
    for log in logs:
        for item in (log.get(key) or []):
            text = str(item).strip()
            if text and text not in values:
                values.append(text)
    return values


def _build_health_snapshot(logs: list[dict], user_profile: dict) -> dict:
    latest = logs[0] if logs else {}
    avg_water = _average_numeric(logs, "water_intake")
    avg_sleep = _average_numeric(logs, "sleep")
    avg_stool = _average_numeric(logs, "stool_passages")
    stress = _latest_non_empty(logs, "stress") or str(user_profile.get("stress_level", "")).strip()
    mood = _latest_non_empty(logs, "mood")
    period_phase = _latest_non_empty(logs, "period_phase")
    cycle_day = latest.get("cycle_day") if isinstance(latest.get("cycle_day"), int) else None

    lines = []
    if avg_water is not None:
        lines.append(f"Hydration average: {avg_water:.1f} L/day")
    if avg_sleep is not None:
        lines.append(f"Sleep average: {avg_sleep:.1f} hours/night")
    if stress:
        lines.append(f"Latest stress context: {stress.title()}")
    if avg_stool is not None:
        lines.append(f"Stool passage average: {avg_stool:.1f} per day")
    if mood:
        lines.append(f"Mood note: {mood}")
    if cycle_day is not None or period_phase:
        bits = []
        if cycle_day is not None:
            bits.append(f"cycle day {cycle_day}")
        if period_phase:
            bits.append(period_phase)
        lines.append(f"Menstrual context: {', '.join(bits)}")
    symptoms = _collect_list_values(logs, "symptoms")[:4]
    if symptoms:
        lines.append(f"Recent symptoms: {', '.join(symptoms)}")
    concerns = _collect_list_values(logs, "skin_concerns")[:4]
    if concerns:
        lines.append(f"Tracked skin concerns: {', '.join(concerns)}")
    return {"summary_lines": lines[:6]}


def _evaluate_image_quality(image_path: Path, confidence: int) -> dict:
    lighting = ("Moderate", "Lighting was acceptable for a screen-level review.")
    visibility = ("Good", "Primary facial regions were available for analysis.")
    clarity = ("Moderate", "Image detail supported overlay generation and lesion review.")
    image = cv2.imread(str(image_path))
    if image is not None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        contrast = float(gray.std())
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if 90 <= brightness <= 185 and contrast >= 35:
            lighting = ("Good", "Uniform brightness and usable contrast were detected across the frame.")
        elif brightness < 70 or brightness > 210:
            lighting = ("Poor", "Lighting was outside the preferred range for stronger confidence.")
        if min(image.shape[0], image.shape[1]) < 720:
            visibility = ("Moderate", "The image was analyzable, though a larger capture would improve facial coverage.")
        if sharpness >= 120:
            clarity = ("Good", "Edge detail supports lesion-level review.")
        elif sharpness < 45:
            clarity = ("Poor", "Blur or compression artifacts may reduce precision.")
    return {
        "lighting": lighting,
        "visibility": visibility,
        "clarity": clarity,
        "overall": confidence,
        "overall_note": "Higher confidence indicates stronger reliability for this screen-level non-diagnostic assessment.",
    }


def _estimate_lesion_mix(acne_count: int, severity: str) -> list[tuple[str, int, str]]:
    if acne_count <= 0:
        return [("Comedones (Estimated)", 0, "No clear comedonal pattern detected."), ("Papules (Estimated)", 0, "No papule-like pattern detected."), ("Pustules (Estimated)", 0, "No pustule-like pattern detected.")]
    if severity in {"Low", "Mild"}:
        comedones = max(1, round(acne_count * 0.55))
        papules = max(0, round(acne_count * 0.3))
    elif severity == "Moderate":
        comedones = max(1, round(acne_count * 0.42))
        papules = max(1, round(acne_count * 0.38))
    else:
        comedones = max(1, round(acne_count * 0.34))
        papules = max(1, round(acne_count * 0.42))
    pustules = max(0, acne_count - comedones - papules)
    return [
        ("Comedones (Estimated)", comedones, "Surface congestion and pore-level activity inferred from visible patterns."),
        ("Papules (Estimated)", papules, "Inflammatory-looking raised lesions estimated from severity cues."),
        ("Pustules (Estimated)", pustules, "Conservative estimate of pustule-like findings for reference only."),
    ]


def _decorate_page(pdf, doc):
    width, height = PAGE_SIZE
    pdf.saveState()
    pdf.setFillColor(colors.HexColor("#FFF7FA"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#FFE6EF"))
    pdf.roundRect(10 * mm, 10 * mm, width - 20 * mm, height - 20 * mm, 8 * mm, fill=1, stroke=0)
    pdf.setFillColor(WHITE)
    pdf.roundRect(14 * mm, 14 * mm, width - 28 * mm, height - 28 * mm, 6 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(BORDER)
    pdf.line(18 * mm, height - 18 * mm, width - 18 * mm, height - 18 * mm)
    if LOGO_PATH.exists():
        try:
            pdf.drawImage(str(LOGO_PATH), 18 * mm, height - 16.5 * mm, width=8 * mm, height=8 * mm, mask="auto")
        except Exception:
            pass
    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(28 * mm, height - 13.5 * mm, "Dermora")
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(TEXT_SOFT)
    pdf.drawRightString(width - 18 * mm, height - 13.5 * mm, f"Page {doc.page}")
    pdf.restoreState()


def _section(title: str, intro: str):
    return [Paragraph(title, STYLES["SectionTitle"]), Paragraph(intro, STYLES["Intro"])]


def _kv_cards(items: list[tuple[str, str, str]], columns: int = 2):
    rows = []
    cards = []
    for label, value, detail in items:
        card = Table([[Paragraph(label, STYLES["Label"])], [Paragraph(value, STYLES["Value"])], [Paragraph(detail, STYLES["Tiny"])]] , colWidths=[118 * mm])
        card.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), PRIMARY_SOFT), ("BOX", (0,0), (-1,-1), 0.7, BORDER), ("LEFTPADDING", (0,0), (-1,-1), 10), ("RIGHTPADDING", (0,0), (-1,-1), 10), ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8)]))
        cards.append(card)
    for index in range(0, len(cards), columns):
        row = cards[index:index + columns]
        while len(row) < columns:
            row.append(Spacer(1, 1))
        table = Table([row], colWidths=[120 * mm] * columns, hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        rows.extend([table, Spacer(1, 7)])
    return rows


def _bullets(items: list[str]):
    return ListFlowable([ListItem(Paragraph(item, STYLES["BodySmall"])) for item in items], bulletType="bullet", leftIndent=12)


def _cover_page(payload):
    user = payload["user"]
    info = [
        ("Date & Time", payload["report_date"], "Timestamp for the generated report."),
        ("Session ID", payload["session_id"], "Unique report session identifier."),
        ("Report Version", REPORT_VERSION, "Current Dermora clinical reference template."),
        ("Analysis Type", ANALYSIS_TYPE, "Generated after image analysis and health-context review."),
    ]
    profile = f"Name: {user.get('name', 'User')}<br/>Age: {user.get('age') or 'Not shared'}<br/>Gender: {user.get('gender') or 'Not shared'}<br/>Skin Type: {user.get('skin_type') or 'Not set'}"
    banner = Table([[Paragraph("AI Skin Health Analysis Report", STYLES["CoverTitle"])], [Paragraph("A comprehensive, AI-supported assessment of visible skin indicators and available health context. This report is non-diagnostic and intended for clinical reference and patient education only.", STYLES["CoverBody"])]] , colWidths=[240 * mm])
    banner.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), PRIMARY), ("BOX", (0,0), (-1,-1), 0, PRIMARY), ("LEFTPADDING", (0,0), (-1,-1), 18), ("RIGHTPADDING", (0,0), (-1,-1), 18), ("TOPPADDING", (0,0), (-1,-1), 18), ("BOTTOMPADDING", (0,0), (-1,-1), 18)]))
    profile_table = Table([[Paragraph("Session Profile", STYLES["Label"]), Paragraph(profile, STYLES["BodySmall"])]] , colWidths=[42 * mm, 198 * mm])
    profile_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), WHITE), ("BOX", (0,0), (-1,-1), 0.7, BORDER), ("LEFTPADDING", (0,0), (-1,-1), 10), ("RIGHTPADDING", (0,0), (-1,-1), 10), ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    return [Spacer(1, 18 * mm), banner, Spacer(1, 10 * mm), *_kv_cards(info), profile_table, PageBreak()]


def _image_quality_page(payload):
    quality = payload["quality"]
    cards = [
        ("Lighting Conditions", quality["lighting"][0], quality["lighting"][1]),
        ("Face Visibility & Alignment", quality["visibility"][0], quality["visibility"][1]),
        ("Resolution & Clarity", quality["clarity"][0], quality["clarity"][1]),
        ("Overall Confidence", f"{quality['overall']}%", quality["overall_note"]),
    ]
    return [*_section("Image Quality Assessment", "Before generating findings, the system reviews image quality to estimate confidence reliability. Lower quality conditions can reduce analytical precision. The uploaded image met the threshold for a screen-level assessment."), *_kv_cards(cards), PageBreak()]


def _summary_page(payload):
    analysis = payload["analysis"]
    cards = [
        ("Skin Health Score", str(analysis.get("score", "--")), "Out of 100. Higher scores indicate fewer visible concerns."),
        ("Total Lesions Detected", str(analysis.get("acne", {}).get("count", 0)), "Visible surface lesions detected across the five primary facial zones."),
        ("Pigmentation Coverage", f"{analysis.get('pigmentation', {}).get('coverage', 0)}%", "Estimated facial area with detectable pigmentation variance."),
        ("Condition Classification", analysis.get("acne", {}).get("severity", "Mild"), analysis.get("summary", "Summary not available.")),
    ]
    return [*_section("Overall Skin Summary", "Detected features, lesion activity, pigmentation coverage, and zone severity are combined into an overall score. This reflects visible indicators only and does not replace a clinical exam."), *_kv_cards(cards), PageBreak()]


def _acne_page(payload):
    analysis = payload["analysis"]
    rows = [(label, str(count), detail) for label, count, detail in payload["lesion_mix"]]
    thresholds = [
        f"Current total lesions: {analysis.get('acne', {}).get('count', 0)}",
        "Reference thresholds: 0-5 Minimal/Clear, 6-15 Mild, 16-30 Moderate, 30+ Severe.",
        f"Current severity band: {analysis.get('acne', {}).get('severity', 'Mild')}",
    ]
    return [*_section("Acne Analysis", "The lesion review maps visible acne-like findings and estimates their relative morphology mix using surface cues only. Counts and morphology notes are non-diagnostic reference indicators."), *_kv_cards(rows, columns=3), Paragraph("Severity Interpretation", STYLES["Label"]), _bullets(thresholds), PageBreak()]


def _zone_page(payload):
    analysis = payload["analysis"]
    rows = [[Paragraph("Zone", STYLES["Label"]), Paragraph("Severity Level", STYLES["Label"]), Paragraph("Lesion Count", STYLES["Label"]), Paragraph("Primary Concern", STYLES["Label"])]]
    for zone, details in analysis.get("zones", {}).items():
        count = int(details.get("count", 0))
        if count == 0:
            concern = "No visible lesion activity"
        elif zone in {"nose", "chin"}:
            concern = "Congestion and oil-zone activity"
        elif zone == "forehead":
            concern = "Clustered breakout activity"
        else:
            concern = "Localized lesion activity"
        rows.append([Paragraph(zone.replace("_", " ").title(), STYLES["BodySmall"]), Paragraph(str(details.get("severity", "Low")), STYLES["BodySmall"]), Paragraph(str(count), STYLES["BodySmall"]), Paragraph(concern, STYLES["BodySmall"])])
    table = Table(rows, colWidths=[52 * mm, 42 * mm, 32 * mm, 110 * mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), PRIMARY_SOFT), ("BOX", (0,0), (-1,-1), 0.7, BORDER), ("INNERGRID", (0,0), (-1,-1), 0.5, BORDER), ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
    return [*_section("Facial Zone Analysis", "The face is segmented into five anatomical zones for localized review. Each zone is independently summarized so care decisions and follow-up observation can be more targeted."), table, PageBreak()]


def _pigmentation_page(payload):
    analysis = payload["analysis"]
    cards = [
        ("Regions Affected", "Dominant review zones", "Surface tone variance was most apparent around the visually active zones in the current session."),
        ("Coverage Estimate", f"{analysis.get('pigmentation', {}).get('coverage', 0)}%", "Estimated facial area showing detectable pigmentation variance."),
        ("Intensity Description", analysis.get("pigmentation", {}).get("intensity", "Low"), "Overall pigmentation intensity classification for the current session."),
    ]
    return [*_section("Pigmentation Analysis", "Pigmentation mapping highlights visible variance in tone relative to the surrounding facial surface. Findings reflect visible discoloration only and do not distinguish between underlying causes without clinical context."), *_kv_cards(cards, columns=3), PageBreak()]


def _visual_page(original_image_path: Path, processed_image_path: Path):
    original = Image(str(original_image_path), width=112 * mm, height=72 * mm) if original_image_path.exists() else Spacer(1, 1)
    processed = Image(str(processed_image_path), width=112 * mm, height=72 * mm) if processed_image_path.exists() else Spacer(1, 1)
    image_table = Table([[Paragraph("Original Capture", STYLES["Label"]), Paragraph("Annotated Output", STYLES["Label"])], [original, processed]], colWidths=[118 * mm, 118 * mm])
    image_table.setStyle(TableStyle([("BOX", (0,0), (-1,-1), 0.7, BORDER), ("INNERGRID", (0,0), (-1,-1), 0.5, BORDER), ("BACKGROUND", (0,0), (-1,0), PRIMARY_SOFT), ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8)]))
    bullets = _bullets([
        "Bounding boxes indicate the approximate location and size of visible lesions.",
        "The annotated output emphasizes the regions where concern density appears stronger.",
        "Facial zones summarize forehead, cheeks, nose, and chin for clearer localization.",
        "Pigmentation notes highlight visible tone variance that may warrant follow-up review.",
    ])
    return [*_section("Visual Explanation Guide", "The generated visuals help explain what the system highlighted during this session. These overlays are intended to make the output easier to review with a clinician or for personal tracking over time."), image_table, Spacer(1, 10), bullets, PageBreak()]


def _insights_page(payload):
    analysis = payload["analysis"]
    health_lines = payload["health"].get("summary_lines") or ["No recent health logs were available for this report."]
    items = []
    for source in (analysis.get("insights", []), analysis.get("correlations", []), health_lines):
        for item in source:
            text = str(item).strip()
            if text and text not in items:
                items.append(text)
    return [*_section("Key Insights", "These observations combine the current image findings with available health-log context. They are intended to support awareness and clinical reference rather than provide diagnosis."), _bullets(items[:8]), PageBreak()]


def _recommendations_page(payload):
    analysis = payload["analysis"]
    health_lines = payload["health"].get("summary_lines") or []
    recommendations = list(analysis.get("recommendations", []))
    if any("Hydration" in line for line in health_lines):
        recommendations.append("Keep hydration entries consistent so future reports can compare skin condition against water intake more clearly.")
    if any("Sleep" in line for line in health_lines):
        recommendations.append("Keep sleep tracking consistent because recovery trends become stronger across repeated sessions.")
    if any("Menstrual context" in line for line in health_lines):
        recommendations.append("Continue menstrual logging when applicable so cyclical flare patterns can be reviewed over time.")
    unique = []
    for item in recommendations:
        text = str(item).strip()
        if text and text not in unique:
            unique.append(text)
    return [*_section("Personalized Recommendations", "These general suggestions are informed by the current session and recent health context. They are not prescriptive treatment instructions and should not replace dermatological advice."), _bullets(unique[:8]), PageBreak()]


def _limitations_page(payload):
    analysis = payload["analysis"]
    previous = payload["previous"]
    progress = (
        f"Previous acne count: {previous.get('acne_count', 'N/A')} | Current acne count: {analysis.get('acne', {}).get('count', 0)} | Trend status: {analysis.get('trend', {}).get('status', 'Baseline')} | Prediction: {analysis.get('prediction', 'Need more history for prediction.')}"
        if previous
        else "No prior analysis was available for this session. Trend comparison becomes more meaningful after at least two completed analyses with supporting health logs."
    )
    cards = [
        ("Overall Model Confidence", f"{analysis.get('confidence', 0)}%", "Confidence reflects image quality, lesion localization consistency, and usable visual detail."),
        ("Pigmentation Detection", analysis.get('pigmentation', {}).get('intensity', 'Low'), "Pigmentation findings reflect visible surface variance only and may shift with lighting conditions."),
        ("Lesion Localization", analysis.get('acne', {}).get('severity', 'Mild'), "Localization accuracy may change with blur, makeup, occlusion, or extreme camera angles."),
    ]
    disclaimer = "This report is generated by an artificial intelligence system for informational, educational, and clinical reference use only. It is not a medical diagnosis, clinical assessment, or substitute for professional dermatological evaluation. Findings reflect visible surface-level indicators and available self-reported health context only. Clinical decisions should always be confirmed by a licensed healthcare professional."
    return [*_section("Confidence, Limitations & Disclaimer", "The values below summarize model confidence, tracking context, and the practical limits of a non-diagnostic visual report."), *_kv_cards(cards, columns=3), Paragraph("Progress Tracking", STYLES["Label"]), Paragraph(progress, STYLES["BodySmall"]), Spacer(1, 8), Paragraph("Important Disclaimer", STYLES["Label"]), Paragraph(disclaimer, STYLES["BodySmall"])]
