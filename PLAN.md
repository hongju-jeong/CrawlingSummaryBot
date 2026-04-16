## 네이버 최신 뉴스 자동 수집 계획

### Summary
FastAPI 백엔드에 `키워드 검색형`이 아니라 `네이버 뉴스 메인 기준 최신 뉴스 자동 수집 크롤러`를 추가한다.  
수집 대상은 네이버 뉴스 메인에 노출되는 최신 기사 목록이며, 각 기사 상세 페이지까지 들어가 `본문(raw_content)`를 저장한다.  
실행 방식은 `수동 실행 API + 10분 주기 자동 실행`을 모두 지원하고, 결과는 PostgreSQL에 적재한다.

### Key Changes
- 크롤러 방향 전환
  - `query` 기반 검색 크롤링은 제외한다.
  - 네이버 뉴스 메인에서 최신 기사 목록을 파싱한다.
  - 목록에서 `제목`, `네이버 기사 링크`, `언론사`, `게시 시각`, `요약 가능 정보`를 추출한다.
  - 기사 상세 페이지까지 진입해 `raw_content`를 수집한다.
  - 크롤러는 네이버 메인 HTML 구조에 맞춘 파서로 구현하고, 실패 시 개별 기사 단위로 skip 처리한다.

- 실행 방식
  - 수동 실행 API
    - `POST /api/crawl/naver-news/latest`
    - body 없이 실행하거나, 선택적으로 `limit`만 받는다
    - 응답은 `requested`, `collected`, `saved`, `skipped`, `failed`
  - 자동 실행
    - APScheduler를 사용해 10분마다 최신 뉴스 수집 작업 실행
    - 앱 시작 시 scheduler 등록
    - 중복 적재 방지 로직을 전제로 반복 실행 가능하게 설계
  - 조회 API
    - `GET /api/issues`는 DB 기준 최근 수집 기사 목록 반환
    - 최신순 정렬 기본
  - 상세 API
    - `GET /api/issues/{issue_id}/preview`는 DB 저장 기사 기준으로 반환
    - 요약이 없으면 placeholder 또는 null-safe 응답 허용

- DB 적재 방식
  - 기존 `sources`, `issues`를 우선 사용
  - `sources`
    - `name='Naver News Main'`
    - `source_type='crawler'`
  - `issues`
    - `source_id`: Naver News Main source id
    - `external_id`: 기사 URL 또는 파싱 가능한 고유 식별자
    - `title`: 기사 제목
    - `original_url`: 기사 상세 링크
    - `category`: 초기값 `'뉴스'`
    - `region`: `NULL`
    - `published_at`: 기사 게시 시각
    - `collected_at`: 수집 시각
    - `raw_content`: 기사 본문
    - `status`: `'collected'`
    - `unique_hash`: URL 기반 hash
  - 중복 방지
    - `unique_hash` 기준 insert-skip 또는 upsert
    - 같은 기사는 재수집 시 새 row를 만들지 않음

- FastAPI 구조
  - `database.py`: SQLAlchemy engine/session
  - `models.py`: `Source`, `Issue`
  - `services/naver_latest_crawler.py`: 메인 목록/기사 본문 파싱
  - `services/issue_ingestion.py`: 정제, dedupe, DB 저장
  - `services/scheduler.py`: 10분 주기 수집 등록
  - `main.py`: startup 시 scheduler 연결, crawl endpoint 등록
  - 현재 `repository.py` 목업 기반 조회는 DB 조회 계층으로 대체

- 설정값
  - `APP_DATABASE_URL`
  - `APP_CRAWLER_TIMEOUT_SECONDS`
  - `APP_CRAWLER_MAX_ITEMS_PER_RUN`
  - `APP_CRAWLER_SCHEDULE_ENABLED`
  - `APP_CRAWLER_INTERVAL_MINUTES=10`
  - `APP_CRAWLER_USER_AGENT`
  - Swagger 문서에 최신 뉴스 수집 API 설명과 예시 추가

### Public APIs / Interfaces
- `POST /api/crawl/naver-news/latest`
  - request
    - `limit: int = 20` 정도를 기본값으로 둠
  - response
    - `requested_count`
    - `collected_count`
    - `saved_count`
    - `skipped_count`
    - `failed_count`
    - `source`
- `GET /api/issues`
  - 현재 프론트 호환 유지
  - `id`, `title`, `source`, `category`, `time`, `report_status`
- `GET /api/issues/{issue_id}/preview`
  - 현재 응답 shape 유지
- 내부 서비스 인터페이스
  - `crawl_latest_news(limit) -> list[CrawledArticle]`
  - `save_crawled_articles(articles) -> IngestionResult`

### Test Plan
- 단위 테스트
  - 메인 뉴스 목록 HTML 파서 검증
  - 기사 본문 파서 검증
  - URL/hash 기반 dedupe 검증
  - 빈 목록, 본문 없음, 링크 없음 케이스 검증
- 통합 테스트
  - `POST /api/crawl/naver-news/latest` 호출 시 정상 응답
  - 수집 직후 `GET /api/issues`에 반영되는지 확인
  - 동일 수집 작업 반복 실행 시 중복 적재가 없는지 확인
- 수동 검증
  - `/docs`에서 최신 뉴스 수집 API 실행
  - DB에 기사 제목/링크/본문이 들어가는지 확인
  - 10분 주기 스케줄이 중복 없이 동작하는지 확인

### Assumptions / Defaults
- 수집 기준은 `네이버 뉴스 메인`이다.
- 키워드 검색 기능은 제외한다.
- 기사 본문까지 수집한다.
- 자동 수집 주기는 `10분`이다.
- 초기 카테고리는 `'뉴스'` 고정으로 저장한다.
- LLM 요약과 Slack 전송은 이번 단계에서 직접 수행하지 않고, 이후 파이프라인이 붙을 수 있게 기사 데이터 적재를 우선한다.
- 네이버 페이지 구조 변경 가능성을 고려해 파서 실패는 전체 실패가 아니라 기사 단위 skip으로 처리한다.
