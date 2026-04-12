from pydantic import BaseModel, Field


class MeshLandmark(BaseModel):
    x: int
    y: int
    z: float = 0.0


class ZonePoint(BaseModel):
    x: int
    y: int


class PigmentationContourPoint(BaseModel):
    x: int
    y: int


class AcneTypeDetection(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    label: str
    raw_label: str = ""
    confidence: float
    color: str = ""


class AnalysisResponse(BaseModel):
    boxes: list[list[int]]
    acne_count: int
    lesion_source: str = "region"
    region_boxes: list[list[int]] = Field(default_factory=list)
    region_count: int = 0
    processed_image_url: str | None = None
    zone_counts: dict[str, int] = Field(default_factory=dict)
    face_detected: bool = False
    landmarks: list[MeshLandmark] = Field(default_factory=list)
    zones: dict[str, list[ZonePoint]] = Field(default_factory=dict)
    pigmentation_contours: list[list[PigmentationContourPoint]] = Field(default_factory=list)
    pigmentation_contour_count: int = 0
    coverage_percentage: float = 0.0
    pigmentation_severity: str = "Low"
    acne_type_available: bool = False
    acne_type_processed_image_url: str | None = None
    acne_type_detections: list[AcneTypeDetection] = Field(default_factory=list)
    acne_type_counts: dict[str, int] = Field(default_factory=dict)
