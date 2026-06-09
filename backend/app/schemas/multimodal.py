from __future__ import annotations

from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float
    width: float
    height: float


class SignatureResult(BaseModel):
    page_number: int
    position: Position
    confidence: float = Field(ge=0.0, le=1.0)


class SealResult(BaseModel):
    page_number: int
    position: Position
    confidence: float = Field(ge=0.0, le=1.0)
    area: float
    circularity: float


class PageAnalysisResponse(BaseModel):
    page_number: int
    has_signature: bool
    has_seal: bool
    signatures: list[SignatureResult]
    seals: list[SealResult]
    ocr_text: str | None = None


class ComplianceIssue(BaseModel):
    severity: str = Field(pattern=r"^(warning|error|critical)$")
    message: str
    recommendation: str


class MultimodalAnalysisResponse(BaseModel):
    filename: str
    total_pages: int
    pages: list[PageAnalysisResponse]
    has_signature: bool
    has_seal: bool
    signature_count: int
    seal_count: int
    compliance_issues: list[ComplianceIssue]
    is_compliant: bool
    processing_time_ms: float
