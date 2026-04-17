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
APP_CRAWLER_SCHEDULE_ENABLED=true
APP_CRAWLER_INTERVAL_MINUTES=10
APP_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
APP_SLACK_AUTO_SEND=true
APP_OPENAI_API_KEY=your_openai_api_key
APP_OPENAI_MODEL=gpt-5.4-mini
```

## Notes

- 기본값은 로컬 실행 편의를 위해 SQLite를 사용하지만 `APP_DATABASE_URL`로 PostgreSQL을 바로 연결할 수 있습니다.
- 네이버 뉴스 메인에서 최신 기사 목록과 본문을 수집해 `sources`, `issues` 테이블에 적재합니다.
- `.env`는 `.gitignore`에 포함되어 있어 git에 올라가지 않습니다.
- `APP_OPENAI_API_KEY`가 설정되면 `issue_summaries`에 실제 `gpt-5.4-mini` 요약 결과를 저장합니다.
- `APP_SLACK_WEBHOOK_URL`이 설정되고 `APP_SLACK_AUTO_SEND=true`이면, 새로 수집된 기사에 대해 AI 요약 텍스트만 Slack으로 자동 전송합니다.
