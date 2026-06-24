# Open Library Subjects MCP Server

Open Library Subjects API로 장르/주제별 도서 목록을 가져오는 Python FastMCP 서버입니다.
API 키 없이 `love`, `history`, `science` 같은 subject를 입력하면 도서 제목, 저자, 첫 출판 연도, Open Library URL을 반환합니다.

## 기능

- `search_subject_books`
  - Open Library subject/genre를 입력받습니다.
  - `https://openlibrary.org/subjects/{subject}.json`을 호출합니다.
  - 도서 제목, 저자, 첫 출판 연도, Open Library URL을 반환합니다.
  - 기본 반환 개수는 5권이고 `limit`으로 1~50권까지 조정할 수 있습니다.
- `GET /health`
  - 서버 상태 확인용 엔드포인트입니다.
- `POST /mcp`
  - FastMCP HTTP transport 엔드포인트입니다.

## 로컬 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python server.py
```

기본 MCP 엔드포인트:

```text
http://localhost:8000/mcp
```

상태 확인:

```bash
curl http://localhost:8000/health
```

## MCP 클라이언트 테스트

서버를 실행한 뒤 다른 터미널에서 실행합니다.

```bash
python - <<'PY'
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool(
            "search_subject_books",
            {"subject": "love", "limit": 3},
        )
        print(result.data)

asyncio.run(main())
PY
```

## 테스트

```bash
source .venv/bin/activate
pytest -q
```

## 파일 구조

```text
.
├── README.md
├── server.py
├── requirements.txt
├── requirements-dev.txt
└── tests/
    └── test_server.py
```

## 참고

- 인증/API 키가 필요 없는 Open Library Subjects API를 사용합니다.
- subject 값은 공백을 underscore로 바꾸고 소문자로 정규화합니다.
- 네트워크/API 오류나 응답 형식 오류는 명확한 예외로 변환합니다.
