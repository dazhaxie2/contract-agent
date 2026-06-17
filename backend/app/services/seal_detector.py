from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from app.core.config import settings


@dataclass
class SealRegion:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    area: float
    circularity: float
    page_number: int = 0


class SealDetector:

    def __init__(self) -> None:
        cfg = settings.multimodal
        self._lower_h = cfg.seal_hsv_lower_h
        self._upper_h = cfg.seal_hsv_upper_h
        self._lower_s = cfg.seal_hsv_lower_s
        self._min_area = cfg.seal_min_area
        self._max_area = cfg.seal_max_area
        self._circularity_threshold = cfg.seal_circularity_threshold

    async def detect(self, page_image: bytes) -> list[SealRegion]:
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("OpenCV not available, seal detection disabled")
            return []

        try:
            nparr = np.frombuffer(page_image, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return []

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            lower_red1 = np.array([self._lower_h, self._lower_s, 50])
            upper_red1 = np.array([self._upper_h, 255, 255])
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)

            lower_red2 = np.array([160, self._lower_s, 50])
            upper_red2 = np.array([180, 255, 255])
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

            mask = cv2.bitwise_or(mask1, mask2)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            regions: list[SealRegion] = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self._min_area or area > self._max_area:
                    continue

                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue

                circularity = (4 * 3.14159265 * area) / (perimeter * perimeter)
                if circularity < self._circularity_threshold:
                    continue

                x, y, w, h = cv2.boundingRect(contour)
                confidence = min(1.0, circularity * 1.2)

                regions.append(
                    SealRegion(
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                        confidence=round(confidence, 3),
                        area=round(area, 1),
                        circularity=round(circularity, 3),
                    )
                )

            return regions

        except Exception as exc:
            logger.error(f"Seal detection failed: {exc}")
            return []


seal_detector = SealDetector()
