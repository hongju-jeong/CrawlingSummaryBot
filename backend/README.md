# FastAPI Backend

## Run

```bash
cd /home/muzy/testp/ai-issue-dashboard-vue
cp .env.example .env
source .venv/bin/activate
uv sync
uvicorn backend.app.main:app --reload
```

## Endpoints

- `GET /health`
- `POST /api/crawl/latest`
- `POST /api/crawl/naver-news/latest`
- `GET /api/issues`
- `GET /api/issues/{issue_id}`
- `GET /api/issues/{issue_id}/preview`
- `GET /api/delivery-logs`

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
APP_CRAWLER_INTERVAL_MINUTES=10
APP_CRAWLER_PROCESSES=4
APP_CRAWLER_CONCURRENCY_PER_PROCESS=8
APP_CRAWLER_HOST_CONCURRENCY=2
APP_GNEWS_API_KEY=
APP_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
APP_SLACK_AUTO_SEND=true
APP_OPENAI_API_KEY=your_openai_api_key
APP_OPENAI_MODEL=gpt-5.4-mini
APP_X_EXPERIMENTAL_ENABLED=false
APP_X_ACCOUNTS=[]
```

## Notes

- 기본값은 로컬 실행 편의를 위해 SQLite를 사용하지만 `APP_DATABASE_URL`로 PostgreSQL을 바로 연결할 수 있습니다.
- 다중 소스 수집기는 네이버, 다음, 연합뉴스, KBS, Reuters, BBC, AP, GNews API를 대상으로 동작합니다.
- `POST /api/crawl/latest`는 멀티프로세스 기반으로 소스 그룹을 병렬 수집합니다.
- `issues.category`는 주제(`정치`, `경제`, `국제`, `산업/기업`, `기술/AI`, `사회`, `연예`)로 사용됩니다.
- `.env`는 `.gitignore`에 포함되어 있어 git에 올라가지 않습니다.
- `APP_OPENAI_API_KEY`가 설정되면 `issue_summaries`에 실제 `gpt-5.4-mini` 요약 결과를 저장합니다.
- `APP_SLACK_WEBHOOK_URL`이 설정되고 `APP_SLACK_AUTO_SEND=true`이면, 새로 수집된 기사에 대해 `[주제] AI 요약` 형식으로 Slack으로 자동 전송합니다.
- `APP_X_EXPERIMENTAL_ENABLED=true`이고 `twscrape` 계정 설정이 준비되면 X 실험 모듈이 별도 그룹으로 동작합니다.
