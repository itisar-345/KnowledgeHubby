from __future__ import annotations

import io
from typing import Optional

import httpx
from fastapi import HTTPException, UploadFile


async def extract_text_from_upload(file: UploadFile) -> str:
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        return _extract_pdf(content)
    if filename.endswith((".txt", ".md")):
        return content.decode("utf-8", errors="replace")

    raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.filename}")


def _extract_pdf(raw: bytes) -> str:
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(raw))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {exc}")


async def fetch_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch URL: {exc}")
