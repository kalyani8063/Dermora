from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

try:
    from mediapipe.solutions.face_mesh import FaceMesh as SolutionsFaceMesh
except Exception:
    SolutionsFaceMesh = None

try:
    from mediapipe.solutions.face_mesh_connections import FACEMESH_TESSELATION as SolutionsFaceMeshTesselation
except Exception:
    SolutionsFaceMeshTesselation = None

try:
    from mediapipe.python.solutions.face_mesh import FaceMesh as PythonSolutionsFaceMesh
except Exception:
    PythonSolutionsFaceMesh = None

try:
    from mediapipe.python.solutions.face_mesh_connections import FACEMESH_TESSELATION as PythonFaceMeshTesselation
except Exception:
    PythonFaceMeshTesselation = None

try:
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
except Exception:
    BaseOptions = None
    FaceLandmarker = None
    FaceLandmarkerOptions = None
    RunningMode = None


ZONE_POINT_INDICES = {
    "forehead": [10, 67, 103, 109, 54, 21, 338, 297, 332, 284, 251, 389, 356],
    "left_cheek": [50, 101, 205, 187, 147, 123, 116, 117, 118, 100, 126, 142, 203, 206],
    "right_cheek": [280, 330, 425, 411, 376, 352, 346, 347, 348, 329, 355, 371, 423, 426],
    "nose": [6, 197, 195, 5, 4, 45, 220, 115, 48, 64, 294, 278, 344, 440, 275],
    "chin": [152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 454, 323, 361, 288, 397, 365, 379],
}

ZONE_COLORS = {
    "forehead": (72, 181, 255),
    "left_cheek": (104, 191, 106),
    "right_cheek": (255, 183, 77),
    "nose": (244, 143, 177),
    "chin": (149, 117, 205),
}

EXCLUSION_POINT_INDICES = {
    "left_eye": [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
    "right_eye": [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398],
    "lips": [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78],
}

DEFAULT_ZONE_COUNTS = {zone_name: 0 for zone_name in ZONE_POINT_INDICES}
DEFAULT_PIGMENTATION_RESULT = {
    "coverage_percentage": 0.0,
    "severity": "Low",
}

_SKIN_YCRCB_LOWER = np.array([0, 133, 77], dtype=np.uint8)
_SKIN_YCRCB_UPPER = np.array([255, 173, 127], dtype=np.uint8)
BACKEND_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BACKEND_DIR / "models"
_FACE_MESH = None
_FACE_MESH_BACKEND = ""
FACE_MESH_TESSELATION = SolutionsFaceMeshTesselation or PythonFaceMeshTesselation or []
ZONE_LABEL_GROUPS = (
    ("Forehead", ("forehead",), 0, -18),
    ("Cheek", ("left_cheek",), -18, -4),
    ("Cheek", ("right_cheek",), 18, -4),
    ("Nose", ("nose",), 0, 8),
    ("Chin/Jawline", ("chin",), 0, 18),
)


def _resolve_candidate_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parents[2] / candidate


def _resolve_face_landmarker_model_path() -> Path | None:
    configured_path = os.getenv("DERMORA_FACE_LANDMARKER_MODEL", "").strip()
    if configured_path:
        candidate = _resolve_candidate_path(configured_path)
        if candidate.is_file():
            return candidate

    model_files = sorted(MODEL_DIR.glob("*.task"))
    return model_files[0] if model_files else None


def _get_face_mesh():
    global _FACE_MESH, _FACE_MESH_BACKEND
    if _FACE_MESH is None:
        model_path = _resolve_face_landmarker_model_path()
        if model_path and FaceLandmarker and FaceLandmarkerOptions and BaseOptions and RunningMode:
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            _FACE_MESH = FaceLandmarker.create_from_options(options)
            _FACE_MESH_BACKEND = "tasks"
        else:
            face_mesh_class = SolutionsFaceMesh or PythonSolutionsFaceMesh
            if face_mesh_class is not None:
                _FACE_MESH = face_mesh_class(
                    static_image_mode=True,
                    max_num_faces=1,
                    refine_landmarks=False,
                    min_detection_confidence=0.5,
                )
                _FACE_MESH_BACKEND = "solutions"
    return _FACE_MESH


def _clamp_point(x: float, y: float, width: int, height: int) -> tuple[int, int]:
    return (
        min(max(int(round(x)), 0), max(width - 1, 0)),
        min(max(int(round(y)), 0), max(height - 1, 0)),
    )


def _serialize_points(points: list[tuple[int, int]]) -> list[dict[str, int]]:
    return [{"x": int(x), "y": int(y)} for x, y in points]


def _serialize_contours(contours: list[np.ndarray]) -> list[list[dict[str, int]]]:
    serialized: list[list[dict[str, int]]] = []
    for contour in contours:
        if contour is None or len(contour) < 3:
            continue
        serialized.append([
            {"x": int(point[0][0]), "y": int(point[0][1])}
            for point in contour
        ])
    return serialized


def _centroid(points: list[tuple[int, int]]) -> tuple[int, int] | None:
    if not points:
        return None

    x_sum = sum(int(point[0]) for point in points)
    y_sum = sum(int(point[1]) for point in points)
    return (round(x_sum / len(points)), round(y_sum / len(points)))


def _polygon_array(points: list[tuple[int, int]]) -> np.ndarray | None:
    if len(points) < 3:
        return None
    return np.array(points, dtype=np.int32)


def _points_to_hull(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) < 3:
        return []

    hull = cv2.convexHull(np.array(points, dtype=np.int32))
    return [tuple(map(int, point[0])) for point in hull]


def _empty_mask(image: np.ndarray) -> np.ndarray:
    return np.zeros(image.shape[:2], dtype=np.uint8)


def _mask_from_regions(image: np.ndarray, region_sets: list[list[tuple[int, int]]], value: int = 255) -> np.ndarray:
    mask = _empty_mask(image)
    for points in region_sets:
        _fill_region(mask, points, value)
    return mask


def _fill_region(mask: np.ndarray, region_points: list[tuple[int, int]], value: int) -> None:
    polygon = _polygon_array(region_points)
    if polygon is not None:
        cv2.fillPoly(mask, [polygon], value)


def _get_landmark_subset(landmarks: list[tuple[int, int]], indices: list[int]) -> list[tuple[int, int]]:
    return [landmarks[index] for index in indices if 0 <= index < len(landmarks)]


def _build_face_mesh_edges(mesh_landmarks: list[dict[str, float | int]]) -> list[tuple[int, int]]:
    if len(mesh_landmarks) < 3:
        return []

    if FACE_MESH_TESSELATION:
        edges: set[tuple[int, int]] = set()
        for connection in FACE_MESH_TESSELATION:
            start_index, end_index = map(int, connection)
            if start_index >= len(mesh_landmarks) or end_index >= len(mesh_landmarks):
                continue
            if start_index == end_index:
                continue
            edge = (min(start_index, end_index), max(start_index, end_index))
            edges.add(edge)
        return sorted(edges)

    x_values = [int(point["x"]) for point in mesh_landmarks]
    y_values = [int(point["y"]) for point in mesh_landmarks]
    face_span = max(max(x_values) - min(x_values), max(y_values) - min(y_values), 1)
    max_distance = max(face_span * 0.09, 18.0)
    max_distance_squared = max_distance * max_distance
    edges: set[tuple[int, int]] = set()

    for index, point in enumerate(mesh_landmarks):
        point_x = float(point["x"])
        point_y = float(point["y"])
        neighbors: list[tuple[float, int]] = []

        for candidate_index, candidate in enumerate(mesh_landmarks):
            if candidate_index == index:
                continue

            dx = point_x - float(candidate["x"])
            dy = point_y - float(candidate["y"])
            distance_squared = (dx * dx) + (dy * dy)
            if distance_squared > max_distance_squared:
                continue
            neighbors.append((distance_squared, candidate_index))

        neighbors.sort(key=lambda item: item[0])
        for _, candidate_index in neighbors[:3]:
            edges.add((min(index, candidate_index), max(index, candidate_index)))

    return sorted(edges)


def _get_depth_stats(mesh_landmarks: list[dict[str, float | int]]) -> tuple[float, float]:
    z_values = [float(point.get("z", 0.0)) for point in mesh_landmarks]
    if not z_values:
        return 0.0, 1.0

    minimum = min(z_values)
    maximum = max(z_values)
    return minimum, max(maximum - minimum, 0.0001)


def _draw_label_box(
    image: np.ndarray,
    text: str,
    anchor: tuple[int, int],
    accent_color: tuple[int, int, int] = (56, 189, 248),
) -> None:
    canvas_height, canvas_width = image.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    padding_x = 8
    padding_y = 6
    box_width = text_width + (padding_x * 2)
    box_height = text_height + baseline + (padding_y * 2)

    raw_x = int(anchor[0] - (box_width / 2))
    raw_y = int(anchor[1] - box_height)
    box_x = min(max(8, raw_x), max(8, canvas_width - box_width - 8))
    box_y = min(max(8, raw_y), max(8, canvas_height - box_height - 8))

    cv2.rectangle(image, (box_x, box_y), (box_x + box_width, box_y + box_height), (15, 23, 42), thickness=-1)
    cv2.rectangle(image, (box_x, box_y), (box_x + box_width, box_y + box_height), accent_color, thickness=1)
    text_origin = (box_x + padding_x, box_y + padding_y + text_height)
    cv2.putText(image, text, text_origin, font, font_scale, (248, 250, 252), thickness, cv2.LINE_AA)


def _normalize_lighting(image: np.ndarray) -> np.ndarray:
    lab_image = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab_image)
    l_equalized = cv2.equalizeHist(l_channel)
    normalized_lab = cv2.merge((l_equalized, a_channel, b_channel))
    return cv2.cvtColor(normalized_lab, cv2.COLOR_LAB2BGR)


def _filter_pigmentation_contours(contours: list[np.ndarray]) -> list[np.ndarray]:
    valid_contours: list[np.ndarray] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area <= 300 or area >= 2000:
            continue

        x, y, width, height = cv2.boundingRect(contour)
        if height == 0:
            continue

        aspect_ratio = width / float(height)
        if 0.5 < aspect_ratio < 2.0:
            valid_contours.append(contour)
    return valid_contours


def _classify_pigmentation_coverage(coverage_percentage: float) -> str:
    if coverage_percentage <= 10:
        return "Low"
    if coverage_percentage <= 20:
        return "Moderate"
    if coverage_percentage <= 30:
        return "High"
    return "Severe"


def detect_face_mesh_landmarks(image: np.ndarray) -> list[dict[str, float | int]]:
    if image is None or image.size == 0:
        return []

    height, width = image.shape[:2]
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    face_mesh = _get_face_mesh()
    if face_mesh is None:
        return []

    if _FACE_MESH_BACKEND == "tasks":
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        results = face_mesh.detect(mp_image)
        if not getattr(results, "face_landmarks", None):
            return []
        raw_landmarks = results.face_landmarks[0]
    else:
        results = face_mesh.process(rgb_image)
        if not results.multi_face_landmarks:
            return []
        raw_landmarks = results.multi_face_landmarks[0].landmark

    landmarks: list[dict[str, float | int]] = []
    for landmark in raw_landmarks:
        x, y = _clamp_point(landmark.x * width, landmark.y * height, width, height)
        landmarks.append({
            "x": x,
            "y": y,
            "z": round(float(getattr(landmark, "z", 0.0)), 6),
        })
    return landmarks


def detect_face_landmarks(image: np.ndarray) -> list[tuple[int, int]]:
    mesh_landmarks = detect_face_mesh_landmarks(image)
    return [(int(point["x"]), int(point["y"])) for point in mesh_landmarks]


def create_face_mask(image: np.ndarray, face_landmarks: list[tuple[int, int]]) -> np.ndarray:
    mask = _empty_mask(image)
    face_polygon = _points_to_hull(face_landmarks)
    polygon = _polygon_array(face_polygon)
    if polygon is not None:
        cv2.fillConvexPoly(mask, polygon, 255)
    return mask


def create_exclusion_mask(image: np.ndarray, face_landmarks: list[tuple[int, int]]) -> np.ndarray:
    exclusion_mask = np.full(image.shape[:2], 255, dtype=np.uint8)
    for feature_indices in EXCLUSION_POINT_INDICES.values():
        feature_points = _points_to_hull(_get_landmark_subset(face_landmarks, feature_indices))
        if feature_points:
            _fill_region(exclusion_mask, feature_points, 0)
    return exclusion_mask


def get_face_zones(landmarks: list[tuple[int, int]]) -> dict[str, list[tuple[int, int]]]:
    zones: dict[str, list[tuple[int, int]]] = {}
    for zone_name, zone_indices in ZONE_POINT_INDICES.items():
        zone_points = _get_landmark_subset(landmarks, zone_indices)
        zones[zone_name] = _points_to_hull(zone_points)
    return zones


def draw_zones(image: np.ndarray, zones: dict[str, list[tuple[int, int]]], alpha: float = 0.18) -> np.ndarray:
    output = image.copy()
    overlay = image.copy()

    for zone_name, zone_points in zones.items():
        polygon = _polygon_array(zone_points)
        if polygon is None:
            continue

        color = ZONE_COLORS.get(zone_name, (180, 180, 180))
        cv2.fillPoly(overlay, [polygon], color)
        cv2.polylines(overlay, [polygon], True, color, 2)

    cv2.addWeighted(overlay, alpha, output, 1 - alpha, 0, output)
    return output


def draw_zone_labels(image: np.ndarray, zones: dict[str, list[tuple[int, int]]]) -> np.ndarray:
    output = image.copy()

    for label, zone_names, offset_x, offset_y in ZONE_LABEL_GROUPS:
        centroids = [_centroid(zones.get(zone_name, [])) for zone_name in zone_names]
        centroids = [point for point in centroids if point is not None]
        if not centroids:
            continue

        average_x = round(sum(point[0] for point in centroids) / len(centroids)) + offset_x
        average_y = round(sum(point[1] for point in centroids) / len(centroids)) + offset_y
        _draw_label_box(output, label, (average_x, average_y), accent_color=(56, 189, 248))

    return output


def draw_face_mesh(image: np.ndarray, mesh_landmarks: list[dict[str, float | int]]) -> np.ndarray:
    if not mesh_landmarks:
        return image.copy()

    output = image.copy()
    edge_overlay = np.zeros_like(image)
    point_overlay = np.zeros_like(image)
    edges = _build_face_mesh_edges(mesh_landmarks)
    min_depth, depth_span = _get_depth_stats(mesh_landmarks)

    for start_index, end_index in edges:
        start_point = mesh_landmarks[start_index]
        end_point = mesh_landmarks[end_index]
        average_depth = (float(start_point.get("z", 0.0)) + float(end_point.get("z", 0.0))) / 2.0
        depth_ratio = min(max((average_depth - min_depth) / depth_span, 0.0), 1.0)

        brightness = int(160 + ((1.0 - depth_ratio) * 55))
        line_color = (brightness, min(255, brightness + 20), 125)
        cv2.line(
            edge_overlay,
            (int(start_point["x"]), int(start_point["y"])),
            (int(end_point["x"]), int(end_point["y"])),
            line_color,
            1,
            cv2.LINE_AA,
        )

    for point in mesh_landmarks:
        depth_ratio = min(max((float(point.get("z", 0.0)) - min_depth) / depth_span, 0.0), 1.0)
        radius = max(1, round(1.0 + ((1.0 - depth_ratio) * 1.6)))
        cv2.circle(
            point_overlay,
            (int(point["x"]), int(point["y"])),
            radius,
            (255, 255, 255),
            thickness=-1,
            lineType=cv2.LINE_AA,
        )

    cv2.addWeighted(edge_overlay, 0.42, output, 1.0, 0, output)
    cv2.addWeighted(point_overlay, 0.65, output, 1.0, 0, output)
    return output


def detect_hyperpigmentation(
    image: np.ndarray,
    face_landmarks: list[tuple[int, int]],
) -> tuple[np.ndarray, list[np.ndarray], float, str]:
    if image is None or image.size == 0:
        return np.zeros((0, 0), dtype=np.uint8), [], 0.0, "Low"

    if not face_landmarks:
        empty_mask = _empty_mask(image)
        return empty_mask, [], 0.0, "Low"

    face_mask = create_face_mask(image, face_landmarks)
    if cv2.countNonZero(face_mask) == 0:
        return face_mask, [], 0.0, "Low"

    exclusion_mask = create_exclusion_mask(image, face_landmarks)

    ycrcb_image = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    skin_mask = cv2.inRange(ycrcb_image, _SKIN_YCRCB_LOWER, _SKIN_YCRCB_UPPER)
    final_skin_mask = cv2.bitwise_and(skin_mask, face_mask)
    final_skin_mask = cv2.bitwise_and(final_skin_mask, exclusion_mask)

    normalized_image = _normalize_lighting(image)
    grayscale = cv2.cvtColor(normalized_image, cv2.COLOR_BGR2GRAY)
    gray_skin = cv2.bitwise_and(grayscale, grayscale, mask=final_skin_mask)

    threshold_mask = cv2.adaptiveThreshold(
        gray_skin,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        15,
        3,
    )
    threshold_mask = cv2.bitwise_and(threshold_mask, final_skin_mask)

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned_mask = cv2.morphologyEx(threshold_mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
    cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)

    contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_contours = _filter_pigmentation_contours(contours)

    contour_mask = _empty_mask(image)
    if valid_contours:
        cv2.drawContours(contour_mask, valid_contours, -1, 255, thickness=cv2.FILLED)

    face_area = max(cv2.countNonZero(face_mask), 1)
    dark_spot_area = cv2.countNonZero(contour_mask)
    coverage_percentage = round((dark_spot_area / float(face_area)) * 100.0, 2)
    severity = _classify_pigmentation_coverage(coverage_percentage)

    return contour_mask, valid_contours, coverage_percentage, severity


def draw_pigmentation(image: np.ndarray, contours: list[np.ndarray]) -> np.ndarray:
    output = image.copy()
    for contour in contours:
        if contour is not None and len(contour) >= 3:
            cv2.drawContours(output, [contour], -1, (255, 0, 0), 2)
    return output


def map_acne_to_zones(
    boxes: list[list[int]],
    zones: dict[str, list[tuple[int, int]]],
) -> dict[str, int]:
    zone_counts = DEFAULT_ZONE_COUNTS.copy()
    polygons = {name: _polygon_array(points) for name, points in zones.items()}

    for box in boxes:
        if len(box) != 4:
            continue

        x1, y1, x2, y2 = box
        center_point = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

        for zone_name, polygon in polygons.items():
            if polygon is None:
                continue
            if cv2.pointPolygonTest(polygon, center_point, False) >= 0:
                zone_counts[zone_name] += 1
                break

    return zone_counts


def draw_acne_boxes(image: np.ndarray, boxes: list[list[int]]) -> np.ndarray:
    output = image.copy()
    for index, box in enumerate(boxes, start=1):
        if len(box) != 4:
            continue

        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(output, (x1, y1), (x2, y2), (34, 197, 94), 2)
        cv2.putText(
            output,
            f"ID {index}",
            (x1, max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (34, 197, 94),
            1,
            cv2.LINE_AA,
        )
    return output


def build_face_analysis_result(image: np.ndarray, yolo_boxes: list[list[int]]) -> dict[str, Any]:
    mesh_landmarks = detect_face_mesh_landmarks(image)
    landmarks = [(int(point["x"]), int(point["y"])) for point in mesh_landmarks]
    zones = get_face_zones(landmarks) if landmarks else {zone_name: [] for zone_name in ZONE_POINT_INDICES}

    annotated_image = image.copy()
    pigmentation_mask = _empty_mask(image)
    pigmentation_contours: list[np.ndarray] = []
    pigmentation_summary = DEFAULT_PIGMENTATION_RESULT.copy()

    if landmarks:
        annotated_image = draw_zones(annotated_image, zones)
        pigmentation_mask, pigmentation_contours, coverage_percentage, severity = detect_hyperpigmentation(image, landmarks)
        annotated_image = draw_pigmentation(annotated_image, pigmentation_contours)
        annotated_image = draw_face_mesh(annotated_image, mesh_landmarks)
        annotated_image = draw_zone_labels(annotated_image, zones)
        pigmentation_summary = {
            "coverage_percentage": coverage_percentage,
            "severity": severity,
        }

    annotated_image = draw_acne_boxes(annotated_image, yolo_boxes)

    return {
        "final_image": annotated_image,
        "zone_counts": map_acne_to_zones(yolo_boxes, zones) if landmarks else DEFAULT_ZONE_COUNTS.copy(),
        "face_detected": bool(landmarks),
        "landmarks": mesh_landmarks,
        "zones": {zone_name: _serialize_points(zone_points) for zone_name, zone_points in zones.items()},
        "pigmentation_contour_points": _serialize_contours(pigmentation_contours),
        "pigmentation_mask": pigmentation_mask,
        "pigmentation_contours": pigmentation_contours,
        "pigmentation": pigmentation_summary,
    }


def process_face(image: np.ndarray, yolo_boxes: list[list[int]]) -> tuple[np.ndarray, dict[str, int]]:
    result = build_face_analysis_result(image, yolo_boxes)
    return result["final_image"], result["zone_counts"]
