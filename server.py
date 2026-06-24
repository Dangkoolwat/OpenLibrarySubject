import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


OPEN_LIBRARY_BASE_URL = "https://openlibrary.org"
USER_AGENT = "open-library-subjects-mcp/1.0"

mcp = FastMCP(
    name="open-library-subjects",
    instructions=(
        "Use this server when the user enters an Open Library subject or genre "
        "and wants book titles, authors, and first publication years for AI book curation."
    ),
)


def validate_subject(subject: str) -> str:
    normalized = re.sub(r"\s+", "_", subject.strip().lower())
    if not normalized:
        raise ValueError("subject must not be empty")
    if not re.fullmatch(r"[a-z0-9_-]{1,80}", normalized):
        raise ValueError("subject must contain only letters, numbers, spaces, hyphens, or underscores")
    return normalized


def validate_limit(limit: int) -> int:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    return limit


def work_url(key: str | None) -> str:
    if not key:
        return OPEN_LIBRARY_BASE_URL
    if key.startswith("/"):
        return f"{OPEN_LIBRARY_BASE_URL}{key}"
    return f"{OPEN_LIBRARY_BASE_URL}/works/{key}"


def normalize_work(work: dict[str, Any]) -> dict[str, Any]:
    authors = [
        author["name"]
        for author in work.get("authors", [])
        if isinstance(author, dict) and author.get("name")
    ]
    return {
        "title": work.get("title") or "Untitled",
        "authors": authors,
        "first_publish_year": work.get("first_publish_year"),
        "openlibrary_url": work_url(work.get("key")),
    }


async def fetch_subject_books(
    subject: str,
    limit: int = 5,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    normalized_subject = validate_subject(subject)
    normalized_limit = validate_limit(limit)
    close_client = client is None
    active_client = client or httpx.AsyncClient(
        timeout=10.0,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        response = await active_client.get(
            f"{OPEN_LIBRARY_BASE_URL}/subjects/{quote(normalized_subject, safe='')}.json",
            params={"limit": normalized_limit},
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Open Library Subjects API request failed") from exc
    finally:
        if close_client:
            await active_client.aclose()

    works = data.get("works")
    if not isinstance(works, list):
        raise RuntimeError("Open Library Subjects API response was invalid")

    return {
        "subject": normalized_subject,
        "name": data.get("name") or normalized_subject,
        "work_count": data.get("work_count", len(works)),
        "books": [normalize_work(work) for work in works if isinstance(work, dict)],
        "source": "Open Library Subjects API",
    }


@mcp.tool(
    name="search_subject_books",
    description="Open Library 주제/장르를 입력받아 도서 제목, 저자, 첫 출판 연도 목록을 제공합니다.",
)
async def search_subject_books(
    subject: str,
    limit: int = 5,
) -> dict[str, Any]:
    result = await fetch_subject_books(subject=subject, limit=limit)
    book_count = len(result["books"])
    return {
        **result,
        "message": (
            f"Open Library에서 '{result['subject']}' 주제 도서 {book_count}권을 찾았습니다. "
            "AI 북 큐레이터에게 전달할 수 있는 제목, 저자, 첫 출판 연도 데이터입니다."
        ),
    }


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "open-library-subjects"})


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    mcp.run(transport="http", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
