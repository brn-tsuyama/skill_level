from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Industry:
    name: str
    category: str
    zip_url: str
    id: int | None = None
    downloaded_at: datetime | None = None
    processed_at: datetime | None = None


@dataclass
class SkillCriterion:
    """One row in the 職務遂行のための基準 section."""

    category: str | None  # 能力細目 label (None when merged from above row)
    criterion_text: str
    criterion_type: str | None  # "●"=エントリー | "■"=サブ | "○"=標準


@dataclass
class SkillSheet:
    """One worksheet inside an ability-unit Excel file == one unit code."""

    industry_id: int
    source_file: str  # path relative to the industry extraction dir
    group_name: str  # subdir name, e.g. "06_00_共通能力ユニット"
    unit_code: str  # normalized, e.g. "06C022L11"
    unit_name: str  # e.g. "段取り"
    unit_summary: str
    excel_type: str  # "A" (10-col 施工技能系) | "B" (7-col 施工管理系)
    level: str  # "L1" | "L2" | "L3" | "L4" | "L3-L4"
    job_type: str  # "施工技能" | "現場管理" | "施工管理" | ""
    criteria: list[SkillCriterion] = field(default_factory=list)
    knowledge: str = ""  # required-knowledge text (concatenated)
    id: int | None = None
