from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from loguru import logger

from app.core.request_context import RequestContext, resolve_request_context
from app.schemas.multimodal import (
    ComplianceIssue,
    MultimodalAnalysisResponse,
    PageAnalysisResponse,
    Position,
    SealResult,
    SignatureResult,
)
from app.services.multimodal_service import multimodal_service

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


@router.post("/analyze", response_model=MultimodalAnalysisResponse)
async def analyze_document(
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(get_request_context),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="file name is required")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="file is empty")

    result = await multimodal_service.analyze_document(
        content=content,
        filename=file.filename,
        tenant_id=ctx.tenant_id,
    )

    compliance_report = await multimodal_service.check_compliance(result, "contract")

    pages = []
    for page in result.pages:
        sigs = [
            SignatureResult(
                page_number=s.page_number or page.page_number,
                position=Position(x=s.x, y=s.y, width=s.width, height=s.height),
                confidence=s.confidence,
            )
            for s in page.signatures
        ]
        seals = [
            SealResult(
                page_number=sl.page_number or page.page_number,
                position=Position(x=sl.x, y=sl.y, width=sl.width, height=sl.height),
                confidence=sl.confidence,
                area=sl.area,
                circularity=sl.circularity,
            )
            for sl in page.seals
        ]
        pages.append(
            PageAnalysisResponse(
                page_number=page.page_number,
                has_signature=page.has_signature,
                has_seal=page.has_seal,
                signatures=sigs,
                seals=seals,
                ocr_text=page.ocr_text,
            )
        )

    compliance_issues = []
    if compliance_report:
        for issue in compliance_report.issues:
            idx = compliance_report.issues.index(issue)
            rec = compliance_report.recommendations[idx] if idx < len(compliance_report.recommendations) else ""
            compliance_issues.append(
                ComplianceIssue(
                    severity="error",
                    message=issue,
                    recommendation=rec,
                )
            )

    return MultimodalAnalysisResponse(
        filename=result.filename,
        total_pages=result.total_pages,
        pages=pages,
        has_signature=result.has_signature,
        has_seal=result.has_seal,
        signature_count=result.signature_count,
        seal_count=result.seal_count,
        compliance_issues=compliance_issues,
        is_compliant=compliance_report.is_compliant if compliance_report else True,
        processing_time_ms=result.processing_time_ms,
    )


@router.post("/check-signatures", response_model=MultimodalAnalysisResponse)
async def check_signatures(
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(get_request_context),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="file name is required")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="file is empty")

    result = await multimodal_service.analyze_document(
        content=content,
        filename=file.filename,
        tenant_id=ctx.tenant_id,
    )

    pages = []
    for page in result.pages:
        sigs = [
            SignatureResult(
                page_number=s.page_number or page.page_number,
                position=Position(x=s.x, y=s.y, width=s.width, height=s.height),
                confidence=s.confidence,
            )
            for s in page.signatures
        ]
        seals = [
            SealResult(
                page_number=sl.page_number or page.page_number,
                position=Position(x=sl.x, y=sl.y, width=sl.width, height=sl.height),
                confidence=sl.confidence,
                area=sl.area,
                circularity=sl.circularity,
            )
            for sl in page.seals
        ]
        pages.append(
            PageAnalysisResponse(
                page_number=page.page_number,
                has_signature=page.has_signature,
                has_seal=page.has_seal,
                signatures=sigs,
                seals=seals,
                ocr_text=None,
            )
        )

    issues = []
    recommendations = []
    is_compliant = True

    if not result.has_signature:
        is_compliant = False
        issues.append("合同缺少签名")
        recommendations.append("请确保合同签署页包含双方签名")
    if not result.has_seal:
        is_compliant = False
        issues.append("合同缺少印章")
        recommendations.append("请确保合同加盖公司公章或合同专用章")

    compliance_issues = [
        ComplianceIssue(severity="error", message=msg, recommendation=recommendations[i] if i < len(recommendations) else "")
        for i, msg in enumerate(issues)
    ]

    return MultimodalAnalysisResponse(
        filename=result.filename,
        total_pages=result.total_pages,
        pages=pages,
        has_signature=result.has_signature,
        has_seal=result.has_seal,
        signature_count=result.signature_count,
        seal_count=result.seal_count,
        compliance_issues=compliance_issues,
        is_compliant=is_compliant,
        processing_time_ms=result.processing_time_ms,
    )
