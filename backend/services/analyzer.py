from pathlib import Path
from datetime import datetime, timezone

import cv2

from backend.schemas.response import (
    AcneDetails,
    AnalysisResponse,
    PigmentationDetails,
    TrendDetails,
    ZoneDetails,
    ZoneSummary,
)
from backend.services.intelligence import generate_insights
from backend.services.ml_model import analyze_image
from backend.services.report import generate_report
from backend.services.workflow import send_to_n8n

ZONE_NAMES = ("forehead", "left_cheek", "right_cheek", "nose", "chin")
ZONE_WEIGHTS = {
    "forehead": 0.3,
    "left_cheek": 0.2,
    "right_cheek": 0.3,
    "nose": 0.1,
    "chin": 0.1,
}


def _severity_from_count(count: int) -> str:
    if count <= 1:
        return "Low"
    if count <= 4:
        return "Mild"
    if count <= 8:
        return "Moderate"
    return "High"


def _zone_severity(count: int) -> str:
    if count <= 2:
        return "Low"
    if count == 3:
        return "Mild"
    return "Moderate"


def _box_severity(box: list[int]) -> str:
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    area = width * height

    if area < 1800:
        return "Low"
    if area < 3000:
        return "Moderate"
    return "High"


def _severity_color(severity: str) -> tuple[int, int, int]:
    colors = {
        "Low": (76, 175, 80),
        "Moderate": (0, 152, 255),
        "High": (64, 64, 255),
    }
    return colors.get(severity, (0, 152, 255))


def draw_overlays(image, boxes):
    canvas = cv2.imread(str(image))
    if canvas is None:
        raise ValueError("Unable to read image for overlay generation.")

    for index, box in enumerate(boxes, start=1):
        severity = _box_severity(box)
        color = _severity_color(severity)
        x1, y1, x2, y2 = box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            canvas,
            f"Acne {index} - {severity}",
            (x1, max(24, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    return canvas


def _build_zones(acne_count: int) -> ZoneDetails:
    base_counts = {}
    remaining = acne_count

    for zone in ZONE_NAMES:
        zone_count = int(acne_count * ZONE_WEIGHTS[zone])
        base_counts[zone] = zone_count
        remaining -= zone_count

    for zone in ZONE_NAMES:
        if remaining <= 0:
            break
        base_counts[zone] += 1
        remaining -= 1

    return ZoneDetails(
        forehead=ZoneSummary(count=base_counts["forehead"], severity=_zone_severity(base_counts["forehead"])),
        left_cheek=ZoneSummary(count=base_counts["left_cheek"], severity=_zone_severity(base_counts["left_cheek"])),
        right_cheek=ZoneSummary(count=base_counts["right_cheek"], severity=_zone_severity(base_counts["right_cheek"])),
        nose=ZoneSummary(count=base_counts["nose"], severity=_zone_severity(base_counts["nose"])),
        chin=ZoneSummary(count=base_counts["chin"], severity=_zone_severity(base_counts["chin"])),
    )


def _top_zone_name(zones: ZoneDetails) -> str:
    zone_map = {
        "forehead": zones.forehead.count,
        "left_cheek": zones.left_cheek.count,
        "right_cheek": zones.right_cheek.count,
        "nose": zones.nose.count,
        "chin": zones.chin.count,
    }
    return max(zone_map, key=zone_map.get)


def _save_processed_image(processed_image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), processed_image)


def _dedupe(items: list[str]) -> list[str]:
    ordered = []
    seen = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def process_skin_analysis(
    image_path: Path,
    image_url: str,
    processed_image_path: Path,
    processed_image_url: str,
    user_profile: dict,
    previous_analysis: dict | None,
    recent_logs: list[dict],
) -> tuple[AnalysisResponse, dict]:
    model_output = analyze_image(image_path)
    acne_count = model_output["acne_count"]
    acne_severity = _severity_from_count(acne_count)
    zones = _build_zones(acne_count)
    pigmentation_coverage = 8
    pigmentation_intensity = "Low"
    score = max(0, 100 - (acne_count * 2) - pigmentation_coverage)
    confidence = 87
    analysis_date = datetime.now(timezone.utc).isoformat()

    processed_image = draw_overlays(image_path, model_output["boxes"])
    _save_processed_image(processed_image, processed_image_path)

    current_context = {
        "acne_count": acne_count,
        "severity": acne_severity,
        "zones": zones.model_dump(),
        "pigmentation": {"coverage": pigmentation_coverage, "intensity": pigmentation_intensity},
    }
    intelligence = generate_insights(current_context, previous_analysis, user_profile, recent_logs)
    previous_count = (previous_analysis or {}).get("acne_count", acne_count)

    report = generate_report(
        {
            "score": score,
            "acne_count": acne_count,
            "severity": acne_severity,
            "pigmentation_coverage": pigmentation_coverage,
            "top_zone": _top_zone_name(zones),
            "confidence": confidence,
        }
    )

    response = AnalysisResponse(
        image_url=image_url,
        processed_image_url=processed_image_url,
        acne=AcneDetails(count=acne_count, severity=acne_severity, boxes=model_output["boxes"]),
        zones=zones,
        pigmentation=PigmentationDetails(coverage=pigmentation_coverage, intensity=pigmentation_intensity),
        score=score,
        confidence=confidence,
        summary=report["summary"],
        insights=_dedupe(report["key_insights"] + intelligence["insights"]),
        recommendations=_dedupe(report["recommendations"] + intelligence["recommendations"]),
        trend=TrendDetails(
            previous_acne_count=previous_count,
            change=intelligence["change"],
            status=intelligence["trend_status"],
        ),
        correlations=intelligence["correlations"],
        prediction=intelligence["prediction"],
        analysis_date=analysis_date,
    )

    workflow_payload = {
        "analysis": response.model_dump(),
        "user": {
            "user_id": user_profile.get("user_id"),
            "name": user_profile.get("name"),
            "age": user_profile.get("age"),
            "gender": user_profile.get("gender"),
            "skin_type": user_profile.get("skin_type"),
        },
        "logs": recent_logs,
        "previous": previous_analysis or {},
    }
    send_to_n8n(workflow_payload)

    analysis_document = {
        "user_id": user_profile["user_id"],
        "date": analysis_date,
        "acne_count": acne_count,
        "severity": acne_severity,
        "zones": zones.model_dump(),
        "pigmentation": {"coverage": pigmentation_coverage, "intensity": pigmentation_intensity},
        "score": score,
        "image_url": image_url,
        "processed_image_url": processed_image_url,
        "summary": response.summary,
        "insights": response.insights,
        "recommendations": response.recommendations,
        "correlations": response.correlations,
        "prediction": response.prediction,
    }

    return response, analysis_document
