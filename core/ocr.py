"""
ocr.py
------
OCR module using pytesseract + OpenCV preprocessing.
Handles image-based quotations (JPG, PNG, scanned PDFs).
"""

import os
import tempfile
import logging
import shutil
import sys
import cv2

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

logger = logging.getLogger(__name__)


def _find_tesseract_cmd() -> str | None:
    # Allow explicit override.
    env_cmd = os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")
    if env_cmd and os.path.exists(env_cmd):
        return env_cmd

    # If it's already on PATH.
    found = shutil.which("tesseract")
    if found:
        return found

    # Common Windows install locations.
    if sys.platform.startswith("win"):
        candidates = [
            os.path.join(os.environ.get("ProgramFiles", ""), "Tesseract-OCR", "tesseract.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Tesseract-OCR", "tesseract.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return p
    return None


def _ensure_tesseract_configured() -> tuple[bool, str]:
    """Return (ready, reason)."""
    if pytesseract is None:
        return False, "pytesseract is not installed"

    cmd = _find_tesseract_cmd()
    if cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
        except Exception:
            # Best-effort; version check below will validate anyway.
            pass

    try:
        _ = pytesseract.get_tesseract_version()
        return True, "ok"
    except Exception:
        # Most common: tesseract.exe missing or not configured.
        return False, "tesseract executable not found (install Tesseract OCR and/or set TESSERACT_CMD)"


def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Run OCR on raw image bytes.

    Pipeline:
        1. Decode bytes → NumPy array (via OpenCV)
        2. Preprocess (grayscale, denoise, threshold)
        3. Pass to pytesseract
        4. Return extracted text string

    Args:
        image_bytes: Raw bytes of the image (PNG, JPEG, etc.)

    Returns:
        str: OCR-extracted text, or an error message if unavailable
    """
    ready, reason = _ensure_tesseract_configured()
    if not ready:
        raise RuntimeError(f"OCR unavailable: {reason}")

    try:
        # Keep dependencies minimal: avoid importing NumPy explicitly.
        # Write bytes to a temporary file and let OpenCV load it.
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".img") as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            img = cv2.imread(tmp_path, cv2.IMREAD_COLOR)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if img is None:
            return "[Could not decode image – unsupported format]"

        # Preprocess for better OCR accuracy
        preprocessed = _preprocess(img)

        # Run Tesseract
        text = pytesseract.image_to_string(preprocessed, config="--oem 3 --psm 6")
        if not text or not str(text).strip():
            raise RuntimeError("No text detected by OCR")
        return str(text).strip()

    except Exception as e:
        logger.exception("OCR error")
        raise RuntimeError(f"OCR error: {e}")


def _preprocess(img):
    """
    Image preprocessing pipeline to improve OCR accuracy on
    documents / quotation scans.

    Steps:
        1. Convert to grayscale
        2. Upscale if image is small (small images hurt OCR accuracy)
        3. Denoise
        4. Adaptive thresholding → clean black/white image

    Args:
        img: OpenCV BGR image array

    Returns:
        Preprocessed grayscale image (OpenCV array)
    """
    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Upscale if needed (minimum 1200px on the longer side)
    h, w = gray.shape
    scale_factor = max(1200 / max(h, w), 1.0)
    if scale_factor > 1.0:
        gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor,
                          interpolation=cv2.INTER_CUBIC)

    # 3. Gaussian denoise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # 4. Adaptive threshold – handles uneven lighting / shadows
    processed = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2
    )

    return processed
