from pydantic import BaseModel


class HealthLogRequest(BaseModel):
    water_intake: float | None = None
    activity: str = ""
    diet: str = ""
    sleep: float | None = None
    stress: str = ""
    menstrual_cycle: str = ""


class HealthTextRequest(BaseModel):
    message: str


class HealthLogResponse(BaseModel):
    message: str
    log: dict
