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


def validate_english_title(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title.strip())
    if not normalized:
        raise ValueError("title must not be empty")
    try:
        normalized.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("title must be English text") from exc
    if not re.search(r"[A-Za-z]", normalized):
        raise ValueError("title must be English text")
    return normalized


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


def normalize_description(description: Any) -> str:
    if isinstance(description, str):
        return description
    if isinstance(description, dict) and isinstance(description.get("value"), str):
        return description["value"]
    return ""


def normalize_edition(edition: dict[str, Any]) -> dict[str, Any]:
    isbn = edition.get("isbn_13") or edition.get("isbn_10") or []
    return {
        "title": edition.get("title") or "Untitled",
        "publish_date": edition.get("publish_date"),
        "publishers": edition.get("publishers") or [],
        "isbn": isbn,
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


async def fetch_book_by_title(
    title: str,
    edition_limit: int = 3,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    normalized_title = validate_english_title(title)
    normalized_edition_limit = validate_limit(edition_limit)
    close_client = client is None
    active_client = client or httpx.AsyncClient(
        timeout=10.0,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        search_response = await active_client.get(
            f"{OPEN_LIBRARY_BASE_URL}/search.json",
            params={"title": normalized_title, "limit": 1},
        )
        search_response.raise_for_status()
        search_data = search_response.json()

        docs = search_data.get("docs") or []
        if not docs:
            raise RuntimeError("No Open Library book found")

        doc = docs[0]
        key = doc.get("key")
        if not key:
            raise RuntimeError("Open Library search response was invalid")

        work_response = await active_client.get(f"{OPEN_LIBRARY_BASE_URL}{key}.json")
        work_response.raise_for_status()
        work_data = work_response.json()

        editions_response = await active_client.get(
            f"{OPEN_LIBRARY_BASE_URL}{key}/editions.json",
            params={"limit": normalized_edition_limit},
        )
        editions_response.raise_for_status()
        editions_data = editions_response.json()
    except RuntimeError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Open Library Search API request failed") from exc
    finally:
        if close_client:
            await active_client.aclose()

    editions = editions_data.get("entries") or []
    subjects = work_data.get("subjects") or doc.get("subject") or []

    return {
        "query": normalized_title,
        "title": work_data.get("title") or doc.get("title") or normalized_title,
        "authors": doc.get("author_name") or [],
        "first_publish_year": doc.get("first_publish_year"),
        "first_publish_date": work_data.get("first_publish_date"),
        "description": normalize_description(work_data.get("description")),
        "subjects": subjects[:10],
        "openlibrary_url": work_url(key),
        "editions": [
            normalize_edition(edition)
            for edition in editions
            if isinstance(edition, dict)
        ],
        "source": "Open Library Search API",
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


@mcp.tool(
    name="search_book_by_title",
    description="영어 책 제목을 입력받아 Open Library 책 상세 정보와 판본 정보를 제공합니다.",
)
async def search_book_by_title(
    title: str,
    edition_limit: int = 3,
) -> dict[str, Any]:
    result = await fetch_book_by_title(title=title, edition_limit=edition_limit)
    authors = ", ".join(result["authors"]) or "Unknown"
    publish_year = result["first_publish_year"] or "unknown"
    return {
        **result,
        "message": (
            f"Open Library에서 '{result['title']}' 책 정보를 찾았습니다. "
            f"저자는 {authors}, 첫 출판 연도는 {publish_year}년입니다."
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
