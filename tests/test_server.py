import httpx
import pytest

from server import (
    fetch_book_by_title,
    fetch_subject_books,
    search_book_by_title,
    search_subject_books,
)


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
async def test_fetch_book_by_title_returns_open_library_book_details():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        if request.url.path == "/search.json":
            assert request.url.params["title"] == "The Road Less Traveled"
            assert request.url.params["limit"] == "1"
            return httpx.Response(
                200,
                json={
                    "numFound": 1,
                    "docs": [
                        {
                            "title": "The Road Less Traveled",
                            "key": "/works/OL2868914W",
                            "author_name": ["M. Scott Peck"],
                            "first_publish_year": 1978,
                        }
                    ],
                },
            )

        if request.url.path == "/works/OL2868914W.json":
            return httpx.Response(
                200,
                json={
                    "title": "The Road Less Traveled",
                    "first_publish_date": "1978",
                    "description": "A book about discipline, love, and spiritual growth.",
                    "subjects": ["Self-actualization (Psychology)", "Spirituality"],
                },
            )

        if request.url.path == "/works/OL2868914W/editions.json":
            assert request.url.params["limit"] == "3"
            return httpx.Response(
                200,
                json={
                    "entries": [
                        {
                            "title": "The road less traveled",
                            "publish_date": "1978",
                            "publishers": ["Simon and Schuster"],
                            "isbn_10": ["0671240862"],
                        }
                    ]
                },
            )

        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_book_by_title(
            "The Road Less Traveled",
            edition_limit=3,
            client=client,
        )

    assert [request.url.path for request in requests] == [
        "/search.json",
        "/works/OL2868914W.json",
        "/works/OL2868914W/editions.json",
    ]
    assert result == {
        "query": "The Road Less Traveled",
        "title": "The Road Less Traveled",
        "authors": ["M. Scott Peck"],
        "first_publish_year": 1978,
        "first_publish_date": "1978",
        "description": "A book about discipline, love, and spiritual growth.",
        "subjects": ["Self-actualization (Psychology)", "Spirituality"],
        "openlibrary_url": "https://openlibrary.org/works/OL2868914W",
        "editions": [
            {
                "title": "The road less traveled",
                "publish_date": "1978",
                "publishers": ["Simon and Schuster"],
                "isbn": ["0671240862"],
            }
        ],
        "source": "Open Library Search API",
    }


@pytest.mark.asyncio
async def test_search_book_by_title_returns_user_friendly_payload(monkeypatch):
    async def fake_fetch_book_by_title(title: str, edition_limit: int = 3):
        return {
            "query": title,
            "title": "The Road Less Traveled",
            "authors": ["M. Scott Peck"],
            "first_publish_year": 1978,
            "first_publish_date": "1978",
            "description": "A book about discipline, love, and spiritual growth.",
            "subjects": ["Self-actualization (Psychology)", "Spirituality"],
            "openlibrary_url": "https://openlibrary.org/works/OL2868914W",
            "editions": [],
            "source": "Open Library Search API",
        }

    monkeypatch.setattr("server.fetch_book_by_title", fake_fetch_book_by_title)

    result = await search_book_by_title("The Road Less Traveled")

    assert result["message"] == (
        "Open Library에서 'The Road Less Traveled' 책 정보를 찾았습니다. "
        "저자는 M. Scott Peck, 첫 출판 연도는 1978년입니다."
    )
    assert result["subjects"] == ["Self-actualization (Psychology)", "Spirituality"]


@pytest.mark.asyncio
async def test_fetch_book_by_title_rejects_non_english_title():
    with pytest.raises(ValueError, match="title must be English text"):
        await fetch_book_by_title("아직도 가야 할 길")


@pytest.mark.asyncio
async def test_fetch_subject_books_rejects_blank_subject():
    with pytest.raises(ValueError, match="subject must not be empty"):
        await fetch_subject_books("   ")


@pytest.mark.asyncio
async def test_fetch_subject_books_rejects_invalid_limit():
    with pytest.raises(ValueError, match="limit must be between 1 and 50"):
        await fetch_subject_books("love", limit=0)
