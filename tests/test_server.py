import httpx
import pytest

from server import fetch_subject_books, search_subject_books


@pytest.mark.asyncio
async def test_fetch_subject_books_returns_open_library_subject_results():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/subjects/love.json"
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json={
                "name": "love",
                "work_count": 12345,
                "works": [
                    {
                        "title": "Pride and Prejudice",
                        "key": "/works/OL66554W",
                        "first_publish_year": 1813,
                        "authors": [{"name": "Jane Austen"}],
                    },
                    {
                        "title": "Jane Eyre",
                        "key": "/works/OL1093073W",
                        "first_publish_year": 1847,
                        "authors": [{"name": "Charlotte Bronte"}],
                    },
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_subject_books(" love ", limit=2, client=client)

    assert len(requests) == 1
    assert result == {
        "subject": "love",
        "name": "love",
        "work_count": 12345,
        "books": [
            {
                "title": "Pride and Prejudice",
                "authors": ["Jane Austen"],
                "first_publish_year": 1813,
                "openlibrary_url": "https://openlibrary.org/works/OL66554W",
            },
            {
                "title": "Jane Eyre",
                "authors": ["Charlotte Bronte"],
                "first_publish_year": 1847,
                "openlibrary_url": "https://openlibrary.org/works/OL1093073W",
            },
        ],
        "source": "Open Library Subjects API",
    }


@pytest.mark.asyncio
async def test_search_subject_books_returns_user_friendly_curator_payload(monkeypatch):
    async def fake_fetch_subject_books(subject: str, limit: int = 5):
        return {
            "subject": subject,
            "name": subject,
            "work_count": 12345,
            "books": [
                {
                    "title": "Pride and Prejudice",
                    "authors": ["Jane Austen"],
                    "first_publish_year": 1813,
                    "openlibrary_url": "https://openlibrary.org/works/OL66554W",
                }
            ],
            "source": "Open Library Subjects API",
        }

    monkeypatch.setattr("server.fetch_subject_books", fake_fetch_subject_books)

    result = await search_subject_books("love", limit=1)

    assert result["message"] == (
        "Open Library에서 'love' 주제 도서 1권을 찾았습니다. "
        "AI 북 큐레이터에게 전달할 수 있는 제목, 저자, 첫 출판 연도 데이터입니다."
    )
    assert result["books"][0]["title"] == "Pride and Prejudice"


@pytest.mark.asyncio
async def test_fetch_subject_books_rejects_blank_subject():
    with pytest.raises(ValueError, match="subject must not be empty"):
        await fetch_subject_books("   ")


@pytest.mark.asyncio
async def test_fetch_subject_books_rejects_invalid_limit():
    with pytest.raises(ValueError, match="limit must be between 1 and 50"):
        await fetch_subject_books("love", limit=0)
