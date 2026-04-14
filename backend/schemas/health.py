from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthLogRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    entry_date: str | None = None
    sugar_free: bool | None = None
    water_intake: float | None = None
    activity: str = ""
    diet: str = ""
    sleep: float | None = None
    stress: str = ""
    menstrual_cycle: str = ""
    menstrual_logged: bool = False
    stool_passages: int | None = Field(default=None, ge=0, le=12)
    stool_feel: str = ""

    mood: str = ""
    energy_level: int | None = Field(default=None, ge=0, le=10)
    symptoms: list[str] = Field(default_factory=list)
    skin_concerns: list[str] = Field(default_factory=list)
    products_used: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)

    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    location: str = ""
    weather: str = ""
    humidity: float | None = Field(default=None, ge=0, le=100)
    uv_index: float | None = Field(default=None, ge=0)

    period_phase: str = ""
    cycle_day: int | None = Field(default=None, ge=1, le=60)
    sleep_quality: str = ""
    workout_minutes: int | None = Field(default=None, ge=0)

    source: str = "manual"
    additional_context: dict[str, Any] = Field(default_factory=dict)


class HealthTextRequest(BaseModel):
    message: str


class HealthLogResponse(BaseModel):
    message: str
    log: dict
    orchestration_event: dict[str, Any] | None = None

