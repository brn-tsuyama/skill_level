from dataclasses import dataclass
from datetime import datetime


@dataclass
class MlitIndustry:
    name: str
    pdf_url: str
    ccus_codes: str | None = None
    evaluation_body: str | None = None
    title: str | None = None
    id: int | None = None
    downloaded_at: datetime | None = None
    processed_at: datetime | None = None


@dataclass
class MlitLevelCriterion:
    """One row in the level-criteria table (就業日数 / 保有資格 / 職長経験 etc.)."""

    industry_id: int
    level: str  # "L1" | "L2" | "L3" | "L4"
    criterion_type: str | None  # "就業日数" | "保有資格" | "職長経験" | None (L1)
    criterion_text: str
