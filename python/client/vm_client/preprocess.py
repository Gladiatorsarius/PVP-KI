from __future__ import annotations

import base64

import cv2
import numpy as np


def to_grayscale(image_bgr: np.ndarray, width: int, height: int) -> np.ndarray:
    resized = cv2.resize(image_bgr, (width, height), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)


def grayscale_to_jpeg_b64(gray: np.ndarray, quality: int = 70) -> str:
    """Encode grayscale image to JPEG base64.
    
    For 64x64 grayscale images, quality is automatically reduced from 70 to 40
    to optimize bandwidth while maintaining acceptable quality for small images.
    """
    # For very small images (64x64), reduce quality further to save bandwidth
    if gray.shape[0] <= 64 and gray.shape[1] <= 64:
        quality = min(quality, 40)  # Reduce quality for small frames
    
    ok, encoded = cv2.imencode(
        ".jpg",
        gray,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
    )
    if not ok:
        raise RuntimeError("jpeg encoding failed")
    # TODO: Consider binary WebSocket protocol instead of base64 to save 33% bandwidth
    return base64.b64encode(encoded.tobytes()).decode("ascii")
