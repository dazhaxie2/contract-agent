from __future__ import annotations

import time
from dataclasses import dataclass, field

from loguru import logger

from app.core.config import settings
from app.services.seal_detector import seal_detector, SealRegion
from app.services.signature_detector import signature_detector, SignatureRegion


@dataclass
class PageAnalysis:
    page_number: int
    has_signature: bool = False
    has_seal: bool = False
    signatures: list[SignatureRegion] = field(default_factory=list)
    seals: list[SealRegion] = field(default_factory=list)
    ocr_text: str | None = None


@dataclass
class ComplianceReport:
    is_compliant: bool = True
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class MultimodalResult:
    filename: str
    total_pages: int = 0
    pages: list[PageAnalysis] = field(default_factory=list)
    has_signature: bool = False
    has_seal: bool = False
    signature_count: int = 0
    seal_count: int = 0
    compliance_report: ComplianceReport | None = None
    processing_time_ms: float = 0.0


class MultimodalService:

    def __init__(self) -> None:
        self._signature_detector = signature_detector
        self._seal_detector = seal_detector

    async def analyze_document(
        self, content: bytes, filename: str, tenant_id: str
    ) -> MultimodalResult:
        start = time.perf_counter()
        result = MultimodalResult(filename=filename)

        if not settings.multimodal.enabled:
            logger.info("Multimodal analysis disabled by config")
            return result

        try:
            import fitz

            doc = fitz.open(stream=content, filetype="pdf")
            result.total_pages = len(doc)

            for page_num in range(result.total_pages):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=150)
                page_image = pix.tobytes("png")

                page_analysis = await self.analyze_page(page_image, page_num + 1)
                result.pages.append(page_analysis)

            doc.close()

        except ImportError:
            logger.warning("PyMuPDF not available for multimodal analysis")
        except Exception as exc:
            logger.error(f"Document analysis failed: {exc}")

        result.signature_count = sum(len(p.signatures) for p in result.pages)
        result.seal_count = sum(len(p.seals) for p in result.pages)
        result.has_signature = result.signature_count > 0
        result.has_seal = result.seal_count > 0

        result.processing_time_ms = round((time.perf_counter() - start) * 1000, 2)
        return result

    async def analyze_page(self, page_image: bytes, page_number: int) -> PageAnalysis:
        analysis = PageAnalysis(page_number=page_number)

        if settings.multimodal.signature_detection_enabled:
            try:
                analysis.signatures = await self._signature_detector.detect(page_image)
                analysis.has_signature = len(analysis.signatures) > 0
            except Exception as exc:
                logger.error(f"Signature detection failed on page {page_number}: {exc}")

        if settings.multimodal.seal_detection_enabled:
            try:
                analysis.seals = await self._seal_detector.detect(page_image)
                analysis.has_seal = len(analysis.seals) > 0
            except Exception as exc:
                logger.error(f"Seal detection failed on page {page_number}: {exc}")

        analysis.ocr_text = await self._run_ocr(page_image)

        return analysis

    async def check_compliance(
        self, analysis: MultimodalResult, contract_type: str
    ) -> ComplianceReport:
        report = ComplianceReport()

        if not analysis.has_signature:
            report.is_compliant = False
            report.issues.append("合同缺少签名")
            report.recommendations.append("请确保合同签署页包含双方签名")

        if not analysis.has_seal:
            report.is_compliant = False
            report.issues.append("合同缺少印章")
            report.recommendations.append("请确保合同加盖公司公章或合同专用章")

        if analysis.total_pages == 0:
            report.is_compliant = False
            report.issues.append("无法解析文档页面")
            report.recommendations.append("请检查PDF文件是否完整且未损坏")

        analysis.compliance_report = report
        return report

    async def _run_ocr(self, page_image: bytes) -> str | None:
        try:
            import cv2
            import numpy as np
            from paddleocr import PaddleOCR

            nparr = np.frombuffer(page_image, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            ocr_result = ocr.ocr(img, cls=True)

            if not ocr_result or not ocr_result[0]:
                return None

            texts = []
            for line in ocr_result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    texts.append(text)

            return "\n".join(texts) if texts else None

        except ImportError:
            logger.debug("PaddleOCR not available for OCR fallback")
            return None
        except Exception as exc:
            logger.error(f"OCR processing failed: {exc}")
            return None


multimodal_service = MultimodalService()
