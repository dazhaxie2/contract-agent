from __future__ import annotations

import asyncio
from dataclasses import dataclass

from loguru import logger


@dataclass
class SignatureRegion:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    page_number: int = 0


class SignatureDetector:

    def __init__(self) -> None:
        self._min_area = 200
        self._max_area = 200000
        self._min_aspect = 0.2
        self._max_aspect = 5.0

    async def detect(self, page_image: bytes) -> list[SignatureRegion]:
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("OpenCV not available, signature detection disabled")
            return []

        try:
            nparr = np.frombuffer(page_image, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return []

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 10
            )

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            regions: list[SignatureRegion] = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self._min_area or area > self._max_area:
                    continue

                x, y, w, h = cv2.boundingRect(contour)
                if h == 0:
                    continue
                aspect = w / h
                if aspect < self._min_aspect or aspect > self._max_aspect:
                    continue

                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                solidity = area / cv2.contourArea(cv2.convexHull(contour)) if cv2.contourArea(cv2.convexHull(contour)) > 0 else 0

                confidence = min(1.0, solidity * (area / self._max_area) * 2)
                confidence = max(0.1, confidence)

                regions.append(
                    SignatureRegion(x=x, y=y, width=w, height=h, confidence=round(confidence, 3))
                )

            return regions

        except Exception as exc:
            logger.error(f"Signature detection failed: {exc}")
            return []


signature_detector = SignatureDetector()
