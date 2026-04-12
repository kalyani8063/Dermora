import os
from pathlib import Path

import cv2

BACKEND_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BACKEND_DIR / "models"
ULTRALYTICS_CONFIG_DIR = BACKEND_DIR / ".ultralytics"
DEFAULT_CONFIDENCE = 0.08
DEFAULT_IMAGE_SIZE = 640
DEFAULT_IOU = 0.7
DEFAULT_MAX_DETECTIONS = 200
ACNE_TYPE_COLOR_MAP = {
    "comedonal": {"hex": "#22c55e", "bgr": (34, 197, 94)},
    "inflammatory": {"hex": "#ef4444", "bgr": (68, 68, 239)},
    "other": {"hex": "#3b82f6", "bgr": (246, 130, 59)},
}

ULTRALYTICS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(ULTRALYTICS_CONFIG_DIR))

from ultralytics import YOLO

_MODEL_CACHE: dict[str, YOLO] = {}


def _get_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _resolve_configured_model_path(env_name: str) -> Path:
    configured_path = os.getenv(env_name, "").strip()
    if configured_path:
        candidate = Path(configured_path)
        if not candidate.is_absolute():
            candidate_options = (
                BACKEND_DIR / candidate,
                BACKEND_DIR.parent / candidate,
            )
        else:
            candidate_options = (candidate,)

        for candidate_path in candidate_options:
            if candidate_path.is_file():
                return candidate_path

    return Path()


def _resolve_model_path() -> Path:
    configured_model = _resolve_configured_model_path("DERMORA_MODEL_PATH")
    if configured_model.is_file():
        return configured_model

    default_model = MODEL_DIR / "best.pt"
    if default_model.is_file():
        return default_model

    discovered_models = sorted(MODEL_DIR.glob("*.pt"))
    if discovered_models:
        return discovered_models[0]

    return Path()


def _resolve_acne_type_model_path() -> Path:
    configured_model = _resolve_configured_model_path("DERMORA_ACNE_TYPE_MODEL_PATH")
    if configured_model.is_file():
        return configured_model

    for filename in ("acne_type.pt", "acne-type.pt", "acne_classifier.pt", "acne-type-model.pt"):
        candidate = MODEL_DIR / filename
        if candidate.is_file():
            return candidate

    return Path()


def _get_model(model_path: Path):
    if not model_path.is_file():
        return None

    cache_key = str(model_path.resolve())
    if cache_key not in _MODEL_CACHE:
        _MODEL_CACHE[cache_key] = YOLO(str(model_path))
    return _MODEL_CACHE[cache_key]


def _predict(model, image, confidence_threshold: float, iou_threshold: float, max_detections: int):
    return model.predict(
        source=image,
        conf=confidence_threshold,
        imgsz=DEFAULT_IMAGE_SIZE,
        iou=iou_threshold,
        max_det=max_detections,
        verbose=False,
    )


def _normalize_acne_type_label(raw_label: str) -> str:
    normalized = str(raw_label or "").strip().lower().replace("-", " ").replace("_", " ")

    if any(keyword in normalized for keyword in ("comedonal", "comedone", "whitehead", "blackhead", "non inflammatory", "noninflammatory")):
        return "comedonal"
    if any(keyword in normalized for keyword in ("inflammatory", "papule", "pustule", "nodule", "cyst", "cystic")):
        return "inflammatory"
    return "other"


def _draw_acne_type_detections(image, detections: list[dict]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    for detection in detections:
        color = detection["color_bgr"]
        x1 = detection["x1"]
        y1 = detection["y1"]
        x2 = detection["x2"]
        y2 = detection["y2"]
        label = f'{detection["label"]} {detection["confidence"]:.2f}'

        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        (text_width, text_height), baseline = cv2.getTextSize(label, font, 0.55, 1)
        label_top = max(0, y1 - text_height - baseline - 8)
        label_bottom = label_top + text_height + baseline + 8
        label_right = min(image.shape[1] - 1, x1 + text_width + 12)
        cv2.rectangle(image, (x1, label_top), (label_right, label_bottom), color, thickness=-1)
        cv2.putText(
            image,
            label,
            (x1 + 6, label_bottom - baseline - 4),
            font,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )


def _resolve_class_name(class_name_map, class_id: int) -> str:
    if isinstance(class_name_map, dict):
        return str(class_name_map.get(class_id, class_id))
    if isinstance(class_name_map, (list, tuple)) and 0 <= class_id < len(class_name_map):
        return str(class_name_map[class_id])
    return str(class_id)


def analyze_image(image_path: str | Path) -> dict:
    image_file = Path(image_path)
    image = cv2.imread(str(image_file))
    if image is None:
        raise ValueError(f"Unable to read image for model inference: {image_file}")

    model_path = _resolve_model_path()
    model = _get_model(model_path)
    if model is None:
        return {"boxes": [], "acne_count": 0}

    confidence_threshold = _get_float_env("DERMORA_MODEL_CONFIDENCE", DEFAULT_CONFIDENCE)
    iou_threshold = _get_float_env("DERMORA_MODEL_IOU", DEFAULT_IOU)
    max_detections = _get_int_env("DERMORA_MODEL_MAX_DET", DEFAULT_MAX_DETECTIONS)

    results = _predict(model, image, confidence_threshold, iou_threshold, max_detections)

    if not results:
        return {"boxes": [], "acne_count": 0}

    prediction = results[0]
    if prediction.boxes is None:
        return {"boxes": [], "acne_count": 0}

    boxes = prediction.boxes.xyxy.cpu().numpy()
    scores = prediction.boxes.conf.cpu().numpy()

    final_boxes: list[list[int]] = []
    for box, score in zip(boxes, scores):
        if float(score) < confidence_threshold:
            continue

        x1, y1, x2, y2 = map(int, box)
        final_boxes.append([x1, y1, x2, y2])

    return {
        "boxes": final_boxes,
        "acne_count": len(final_boxes),
    }


def analyze_acne_types(image_path: str | Path, processed_image_path: str | Path | None = None) -> dict:
    image_file = Path(image_path)
    image = cv2.imread(str(image_file))
    if image is None:
        raise ValueError(f"Unable to read image for acne-type inference: {image_file}")

    model_path = _resolve_acne_type_model_path()
    model = _get_model(model_path)
    if model is None:
        return {
            "available": False,
            "processed_image_saved": False,
            "detections": [],
            "counts": {"comedonal": 0, "inflammatory": 0, "other": 0},
        }

    confidence_threshold = _get_float_env("DERMORA_ACNE_TYPE_MODEL_CONFIDENCE", _get_float_env("DERMORA_MODEL_CONFIDENCE", DEFAULT_CONFIDENCE))
    iou_threshold = _get_float_env("DERMORA_ACNE_TYPE_MODEL_IOU", _get_float_env("DERMORA_MODEL_IOU", DEFAULT_IOU))
    max_detections = _get_int_env("DERMORA_ACNE_TYPE_MODEL_MAX_DET", _get_int_env("DERMORA_MODEL_MAX_DET", DEFAULT_MAX_DETECTIONS))

    results = _predict(model, image, confidence_threshold, iou_threshold, max_detections)
    if not results:
        return {
            "available": True,
            "processed_image_saved": False,
            "detections": [],
            "counts": {"comedonal": 0, "inflammatory": 0, "other": 0},
        }

    prediction = results[0]
    if prediction.boxes is None:
        return {
            "available": True,
            "processed_image_saved": False,
            "detections": [],
            "counts": {"comedonal": 0, "inflammatory": 0, "other": 0},
        }

    boxes = prediction.boxes.xyxy.cpu().numpy()
    scores = prediction.boxes.conf.cpu().numpy()
    class_ids = prediction.boxes.cls.cpu().numpy().astype(int)
    class_name_map = getattr(prediction, "names", None) or getattr(model, "names", {}) or {}

    detections: list[dict] = []
    counts = {"comedonal": 0, "inflammatory": 0, "other": 0}

    for box, score, class_id in zip(boxes, scores, class_ids):
        if float(score) < confidence_threshold:
            continue

        x1, y1, x2, y2 = map(int, box)
        raw_label = _resolve_class_name(class_name_map, int(class_id))
        normalized_label = _normalize_acne_type_label(raw_label)
        color_config = ACNE_TYPE_COLOR_MAP[normalized_label]
        detections.append(
            {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "label": normalized_label,
                "raw_label": raw_label,
                "confidence": round(float(score), 4),
                "color": color_config["hex"],
                "color_bgr": color_config["bgr"],
            }
        )
        counts[normalized_label] += 1

    processed_image_saved = False
    if processed_image_path:
        annotated_image = image.copy()
        _draw_acne_type_detections(annotated_image, detections)
        target_path = Path(processed_image_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        processed_image_saved = cv2.imwrite(str(target_path), annotated_image)

    response_detections = [
        {
            "x1": detection["x1"],
            "y1": detection["y1"],
            "x2": detection["x2"],
            "y2": detection["y2"],
            "label": detection["label"],
            "raw_label": detection["raw_label"],
            "confidence": detection["confidence"],
            "color": detection["color"],
        }
        for detection in detections
    ]

    return {
        "available": True,
        "processed_image_saved": processed_image_saved,
        "detections": response_detections,
        "counts": counts,
    }
