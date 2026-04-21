# FastAPI Backend

## Run

```bash
cd /home/muzy/testp/ai-issue-dashboard-vue
cp .env.example .env
source .venv/bin/activate
uv sync
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger:

- `http://127.0.0.1:8000/docs`
- WSL 환경에서는 `http://<WSL-IP>:8000/docs`

## Endpoints

- `GET /health`
- `GET /api/runtime-profile`
- `POST /api/crawl/latest`
- `GET /api/crawl/latest/stream`
- `POST /api/crawl/latest/stop`
- `POST /api/crawl/naver-news/latest`
- `GET /api/issues`
- `GET /api/issues/{issue_id}`
- `GET /api/issues/{issue_id}/preview`
- `GET /api/daily-summaries/latest`
- `POST /api/daily-summaries/run`
- `GET /api/delivery-logs`

## Structure

백엔드는 역할 기준으로 아래처럼 나눕니다.

```text
backend/app/
  api/
    routes/
      crawl.py
      delivery_logs.py
      health.py
      issues.py
      runtime_profile.py
  services/
    crawling/
      gnews_api_crawler.py
      html_source_crawler.py
      multi_source_crawler.py
      naver_latest_crawler.py
      source_registry.py
      source_types.py
      x_experimental_crawler.py
    ingestion/
      issue_ingestion.py
      topic_classifier.py
    reporting/
      daily_digest_retrieval.py
      daily_summary.py
      openai_summary.py
      slack_reporter.py
    runtime/
      crawl_control.py
      runtime_profile.py
      scheduler.py
  config.py
  database.py
  models.py
  repository.py
  schemas.py
  main.py
```

### Module ownership

- `api/routes`
  - FastAPI 엔드포인트만 둡니다.
  - 요청/응답 조립과 HTTP 예외 처리만 담당합니다.
- `services/crawling`
  - 외부 소스에서 데이터를 가져오는 로직만 둡니다.
  - 새 뉴스 소스 추가는 이 디렉토리 안에서 끝나는 것이 목표입니다.
- `services/ingestion`
  - 중복 체크, 저장, 임시 주제 분류, 후처리 큐 등록을 담당합니다.
- `services/reporting`
  - OpenAI 기반 기사 분석, LangChain 기반 daily digest retrieval, Slack 전송, 일일 키워드 다이제스트 생성/전송을 담당합니다.
- `services/runtime`
  - 스케줄링, 런타임 튜닝, 머신 스펙 기반 추천값 계산, 수집 취소 제어를 담당합니다.
- `repository.py`
  - 읽기 전용 조회와 응답 변환을 담당합니다.
- `main.py`
  - 앱 생성과 라우터 등록만 담당합니다.

### Change boundaries

기능 브랜치를 작게 유지하려면 아래 기준을 따릅니다.

- 새 크롤러 추가
  - `services/crawling/*`
- 주제 분류/저장 정책 변경
  - `services/ingestion/*`
- AI 요약/Slack 포맷 변경
  - `services/reporting/*`
- 실행 프로필/스케줄 변경
  - `services/runtime/*`
- API 응답 형식 변경
  - `api/routes/*`, `schemas.py`, `repository.py`

## Environment

```bash
cp .env.example .env
```

`.env` 파일을 열어서 필요한 값을 수정합니다.

예시:

```env
APP_DATABASE_URL=sqlite:///./app.db
APP_CRAWLER_TIMEOUT_SECONDS=10
APP_CRAWLER_MAX_ITEMS_PER_RUN=20
APP_CRAWLER_LIMIT_PER_SOURCE=5
APP_CRAWLER_SCHEDULE_ENABLED=true
APP_CRAWLER_INTERVAL_MINUTES=30
APP_CRAWLER_RESPECT_ROBOTS=true
APP_CRAWLER_ROBOTS_CACHE_TTL_SECONDS=3600
APP_CRAWLER_ROBOTS_USER_AGENT=*
APP_CRAWLER_PROCESSES=4
APP_CRAWLER_CONCURRENCY_PER_PROCESS=8
APP_CRAWLER_HOST_CONCURRENCY=2
APP_REPORT_WORKER_THREADS=4
APP_GNEWS_API_KEY=
APP_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/your/webhook/url"
APP_DAILY_SUMMARY_ENABLED=true
APP_DAILY_SUMMARY_WEBHOOK_URL="https://hooks.slack.com/services/your/daily-digest/webhook"
APP_DAILY_SUMMARY_CHANNEL="#news-daily-digest"
APP_DAILY_SUMMARY_CRON_HOUR=0
APP_DAILY_SUMMARY_CRON_MINUTE=0
APP_TOPIC_WEBHOOKS={"정치":"https://hooks.slack.com/services/your/politics/webhook","경제":"https://hooks.slack.com/services/your/economy/webhook","국제":"https://hooks.slack.com/services/your/global/webhook","산업/기업":"https://hooks.slack.com/services/your/business/webhook","기술/AI":"https://hooks.slack.com/services/your/tech/webhook","사회":"https://hooks.slack.com/services/your/society/webhook","연예":"https://hooks.slack.com/services/your/entertainment/webhook"}
APP_TOPIC_CHANNELS={"정치":"#news-politics","경제":"#news-economy","국제":"#news-global","산업/기업":"#news-business","기술/AI":"#news-tech","사회":"#news-society","연예":"#news-entertainment"}
APP_SLACK_AUTO_SEND=true
APP_OPENAI_API_KEY=your_openai_api_key
APP_OPENAI_MODEL=gpt-5.4-mini
APP_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
APP_DAILY_SUMMARY_RAG_ENABLED=true
APP_DAILY_SUMMARY_RAG_LOOKBACK_DAYS=3
APP_DAILY_SUMMARY_RAG_TOP_K=4
APP_X_EXPERIMENTAL_ENABLED=false
APP_X_ACCOUNTS=[]
```

## Notes

- 기본값은 로컬 실행 편의를 위해 SQLite를 사용하지만 `APP_DATABASE_URL`로 PostgreSQL을 바로 연결할 수 있습니다.
- 다중 소스 수집기는 네이버, 다음, 연합뉴스, KBS, Reuters, BBC, AP, GNews API를 대상으로 동작합니다.
- `POST /api/crawl/latest`와 `GET /api/crawl/latest/stream`은 멀티프로세스 기반으로 소스 그룹을 병렬 수집합니다.
- `GET /api/crawl/latest/stream`는 프론트의 실시간 모니터링 이벤트 소스입니다.
- `POST /api/crawl/latest/stop`는 수동 수집 실행 중 cooperative cancellation을 요청합니다.
- HTML 기반 크롤러는 기본적으로 `robots.txt`를 조회하고 `Allow/Disallow` 및 `crawl-delay`를 존중합니다.
- 기사 저장과 중복 체크는 순차로 처리하고, 후처리(OpenAI/Slack)는 `APP_REPORT_WORKER_THREADS` 기준 멀티스레드 worker로 병렬 처리합니다.
- `issues.category`는 주제(`정치`, `경제`, `국제`, `산업/기업`, `기술/AI`, `사회`, `연예`)로 사용됩니다.
- `.env`는 `.gitignore`에 포함되어 있어 git에 올라가지 않습니다.
- 저장 시점의 rule-based 분류는 임시값입니다. 최종 주제는 OpenAI가 `topic + summary`를 함께 생성하는 후처리 단계에서 확정됩니다.
- `APP_OPENAI_API_KEY`가 설정되면 `issue_summaries`에 실제 `gpt-5.4-mini` 결과를 저장합니다. 이때 요약, 최종 주제, 중요도, 핵심 포인트, 리서치 포인트, 추적 키워드를 한 번의 OpenAI 호출로 처리합니다.
- `APP_OPENAI_EMBEDDING_MODEL`이 설정되면 기사 분석 결과를 바탕으로 `issue_embeddings`를 생성해 daily digest용 semantic retrieval에 사용합니다.
- `APP_SLACK_WEBHOOK_URL`이 설정되고 `APP_SLACK_AUTO_SEND=true`이면, 새로 수집된 기사에 대해 중요도에 따라 기본 카드 또는 리서치 카드 형식으로 Slack으로 자동 전송합니다.
- `APP_TOPIC_WEBHOOKS`와 `APP_TOPIC_CHANNELS`를 설정하면, 주제별로 다른 Slack 채널과 webhook으로 라우팅합니다.
- `APP_TOPIC_WEBHOOKS`와 `APP_TOPIC_CHANNELS`는 JSON 한 줄 형식과 여러 줄 딕셔너리 형식을 모두 허용합니다.
- `APP_DAILY_SUMMARY_ENABLED=true`이면 매일 자정에 전날 기준 사건 클러스터 기반 일일 키워드 다이제스트를 전용 Slack 채널로 전송합니다.
- daily digest는 키워드 선정은 규칙 기반으로 유지하고, 키워드 설명 생성 전에 LangChain 기반 retrieval로 관련 기사 문맥을 검색합니다.
- `APP_DAILY_SUMMARY_RAG_ENABLED`, `APP_DAILY_SUMMARY_RAG_LOOKBACK_DAYS`, `APP_DAILY_SUMMARY_RAG_TOP_K`로 retrieval 범위를 조정할 수 있습니다.
- `POST /api/daily-summaries/run`으로 특정 날짜의 다이제스트를 Swagger에서 수동 생성/전송할 수 있습니다.
- 프론트 `전날 요약` 탭의 `요약 테스트` 버튼도 같은 수동 실행 API를 사용합니다.
- 자동 크롤링은 앱 시작 즉시 arm되지 않습니다. 첫 수동 수집이 성공적으로 끝난 뒤에만 interval 잡이 활성화됩니다.
- 프론트는 `모니터링` 탭과 `전날 요약` 탭으로 나뉘며, 후자는 최근 daily digest와 토픽별 키워드를 표시하고 요약 테스트를 바로 실행할 수 있습니다.
- 스포츠 기사는 `연예` 주제로 함께 분류합니다.
- `APP_X_EXPERIMENTAL_ENABLED=true`이고 `twscrape` 계정 설정이 준비되면 X 실험 모듈이 별도 그룹으로 동작합니다.

## Testing

```bash
.venv/bin/pytest -q
```

- 테스트는 운영 `app.db` 대신 전용 임시 SQLite DB를 사용합니다.
- 테스트용 SQLite 경로는 세션별 임시 파일로 분리됩니다.
- 즉 테스트 실행이 로컬 운영 데이터베이스를 직접 초기화하거나 오염시키지 않습니다.
