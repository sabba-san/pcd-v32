"""Helpers for extracting images from uploaded PDF defect reports."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from pypdf import PdfReader


def extract_pdf_images(pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
    """Extract embedded images from *pdf_path* into *output_dir*.

    Returns metadata for each saved image so the caller can build UI links.
    """

    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.exists():
        raise FileNotFoundError(pdf_path)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(pdf_path_obj))
    extracted: List[Dict[str, Any]] = []
    counter = 0

    for page_number, page in enumerate(reader.pages, start=1):
        images = getattr(page, "images", []) or []
        for image_index, image in enumerate(images, start=1):
            counter += 1
            image_format = (getattr(image, "image_format", "png") or "png").lower()
            if image_format == "jpeg":
                image_format = "jpg"

            filename = f"page{page_number:02d}_img{image_index:02d}_{counter}.{image_format}"
            filepath = output_path / filename

            with open(filepath, "wb") as image_file:
                image_file.write(image.data)

            extracted.append(
                {
                    "id": f"img_{counter}",
                    "file": filename,
                    "page": page_number,
                    "width": getattr(image, "width", None),
                    "height": getattr(image, "height", None),
                }
            )

    return extracted
