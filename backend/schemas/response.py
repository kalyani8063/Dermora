from pydantic import BaseModel


class ZoneSummary(BaseModel):
    count: int
    severity: str


class ZoneDetails(BaseModel):
    forehead: ZoneSummary
    left_cheek: ZoneSummary
    right_cheek: ZoneSummary
    nose: ZoneSummary
    chin: ZoneSummary


class AcneDetails(BaseModel):
    count: int
    severity: str
    boxes: list[list[int]]


class PigmentationDetails(BaseModel):
    coverage: int
    intensity: str


class TrendDetails(BaseModel):
    previous_acne_count: int
    change: int
    status: str


class ReportArtifact(BaseModel):
    report_id: str
    session_id: str
    filename: str


class AnalysisResponse(BaseModel):
    image_url: str
    processed_image_url: str
    acne: AcneDetails
    zones: ZoneDetails
    pigmentation: PigmentationDetails
    score: int
    confidence: int
    summary: str
    insights: list[str]
    recommendations: list[str]
    trend: TrendDetails
    correlations: list[str]
    prediction: str
    analysis_date: str
    report: ReportArtifact | None = None
