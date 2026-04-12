from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import cv2

from backend.services.face_analysis import build_face_analysis_result
from backend.services.ml_model import analyze_acne_types, analyze_image


def process_skin_analysis(
    image_path: Path,
    image_url: str,
    processed_image_path: Path,
    processed_image_url: str,
    acne_type_processed_image_path: Path,
    acne_type_processed_image_url: str,
    user_profile: dict,
    previous_analysis: dict | None,
    recent_logs: list[dict],
) -> tuple[dict, dict]:
    region_output = analyze_image(image_path)
    acne_type_output = analyze_acne_types(image_path, acne_type_processed_image_path)
    analysis_date = datetime.now(timezone.utc).isoformat()
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Unable to load image for face analysis: {image_path}")

    acne_type_boxes = [
        [detection["x1"], detection["y1"], detection["x2"], detection["y2"]]
        for detection in acne_type_output["detections"]
    ]
    lesion_boxes = acne_type_boxes or region_output["boxes"]
    lesion_count = len(lesion_boxes)
    lesion_source = "acne_type" if acne_type_boxes else "region"

    face_result = build_face_analysis_result(image, lesion_boxes)
    processed_image_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(processed_image_path), face_result["final_image"]):
        raise ValueError(f"Unable to save processed analysis image: {processed_image_path}")

    response_payload = {
        "boxes": lesion_boxes,
        "acne_count": lesion_count,
        "lesion_source": lesion_source,
        "region_boxes": region_output["boxes"],
        "region_count": region_output["acne_count"],
        "processed_image_url": processed_image_url,
        "zone_counts": face_result["zone_counts"],
        "face_detected": face_result["face_detected"],
        "landmarks": face_result["landmarks"],
        "zones": face_result["zones"],
        "pigmentation_contours": face_result["pigmentation_contour_points"],
        "pigmentation_contour_count": len(face_result["pigmentation_contours"]),
        "coverage_percentage": face_result["pigmentation"]["coverage_percentage"],
        "pigmentation_severity": face_result["pigmentation"]["severity"],
        "acne_type_available": acne_type_output["available"],
        "acne_type_processed_image_url": acne_type_processed_image_url if acne_type_output["processed_image_saved"] else None,
        "acne_type_detections": acne_type_output["detections"],
        "acne_type_counts": acne_type_output["counts"],
    }

    analysis_document = {
        "user_id": user_profile["user_id"],
        "date": analysis_date,
        "image_url": image_url,
        "processed_image_url": processed_image_url,
        "acne_count": lesion_count,
        "boxes": lesion_boxes,
        "lesion_source": lesion_source,
        "region_boxes": region_output["boxes"],
        "region_count": region_output["acne_count"],
        "zone_counts": face_result["zone_counts"],
        "face_detected": face_result["face_detected"],
        "landmarks": face_result["landmarks"],
        "zones": face_result["zones"],
        "pigmentation_contours": face_result["pigmentation_contour_points"],
        "pigmentation_contour_count": len(face_result["pigmentation_contours"]),
        "coverage_percentage": face_result["pigmentation"]["coverage_percentage"],
        "pigmentation_severity": face_result["pigmentation"]["severity"],
        "acne_type_available": acne_type_output["available"],
        "acne_type_processed_image_url": acne_type_processed_image_url if acne_type_output["processed_image_saved"] else None,
        "acne_type_detections": acne_type_output["detections"],
        "acne_type_counts": acne_type_output["counts"],
    }

    return response_payload, analysis_document
