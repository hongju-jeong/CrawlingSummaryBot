# AI Issue Monitoring Dashboard

뉴스와 외부 신호를 수집하고, AI가 요약한 뒤, 주제별 Slack 채널로 자동 보고하는 실시간 모니터링 대시보드입니다.

Vue 프론트엔드에서 수집 진행 상태를 실시간으로 모니터링할 수 있고, FastAPI 백엔드는 멀티소스 크롤링, AI 요약, 주제 분류, Slack 전송을 처리합니다.

## What It Does

- 국내외 뉴스 소스를 주기적으로 수집합니다.
- 수집한 기사를 DB에 저장하고 중복을 제거합니다.
- OpenAI로 `주제 + 요약`을 한 번에 생성합니다.
- 분류된 주제에 따라 서로 다른 Slack 채널로 전송합니다.
- 매일 자정에 전날 기사 기준 토픽별 Top 3 키워드 다이제스트를 전용 Slack 채널로 전송합니다.
- 프론트 대시보드에서 진행 상황, 이슈 리스트, AI 요약, 전송 로그를 실시간으로 확인할 수 있습니다.

## Key Features

- 다중 소스 뉴스 크롤링
  - Naver, Daum, 연합뉴스, KBS, BBC, AP, GNews API
- AI 후처리
- `gpt-5.4-mini` 기반 기사 요약
  - LLM 기반 주제 분류 및 중요도/리서치 포인트 생성
- 주제별 Slack 라우팅
  - `정치`, `경제`, `국제`, `산업/기업`, `기술/AI`, `사회`, `연예`
- 일일 키워드 다이제스트
  - 사건 클러스터 기반 토픽별 Top 3 키워드
- 실시간 모니터링 UI
  - 크롤링 프로세스 수
  - 기사별 처리 단계
  - 실시간 이벤트 피드
  - 전송 로그
- 환경 적응형 실행 프로필
  - 머신 스펙 기반 추천 프로세스/동시성 표시

## Tech Stack

- Frontend: Vue 3, Vite
- Backend: FastAPI, SQLAlchemy
- Crawling: httpx, BeautifulSoup
- AI: OpenAI Responses API
- Delivery: Slack Incoming Webhook
- Storage: SQLite / PostgreSQL

## Project Structure

```text
ai-issue-dashboard-vue/
  backend/         # FastAPI backend and backend docs
  src/             # Vue frontend
  db/              # schema and ERD
  tests/           # backend tests
  .env.example     # environment variable example
  README.md        # project overview
```

세부 백엔드 구조와 실행 문서는 [backend/README.md](backend/README.md) 에 있습니다.

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd ai-issue-dashboard-vue
cp .env.example .env
```

### 2. Backend

```bash
source .venv/bin/activate
uv sync
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend

다른 터미널에서 실행:

```bash
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### 4. Open in browser

- Frontend: `http://<your-host>:5173`
- Swagger: `http://<your-host>:8000/docs`

WSL 환경에서는 `127.0.0.1` 대신 WSL IP로 접속해야 할 수 있습니다.

## Environment

중요한 설정 예시:

```env
APP_OPENAI_API_KEY=your_openai_api_key
APP_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/default/webhook
APP_DAILY_SUMMARY_WEBHOOK_URL=https://hooks.slack.com/services/daily/digest
APP_CRAWLER_RESPECT_ROBOTS=true
APP_TOPIC_WEBHOOKS={"정치":"...","경제":"...","국제":"...","산업/기업":"...","기술/AI":"...","사회":"...","연예":"..."}
APP_TOPIC_CHANNELS={"정치":"#news-politics","경제":"#news-economy","국제":"#news-global","산업/기업":"#news-business","기술/AI":"#news-tech","사회":"#news-society","연예":"#news-entertainment"}
```

전체 환경변수 설명은 [backend/README.md](backend/README.md) 에 있습니다.

## Workflow

1. 뉴스 수집
2. 중복 체크 및 DB 저장
3. OpenAI가 `주제 + 요약` 생성
4. 주제별 Slack 채널 선택
5. Slack 전송 및 로그 저장
6. 자정에 전날 기준 일일 키워드 다이제스트 생성/전송
7. 프론트 대시보드에 실시간 반영

## API Overview

- `GET /health`
- `GET /api/runtime-profile`
- `POST /api/crawl/latest`
- `POST /api/crawl/naver-news/latest`
- `GET /api/issues`
- `GET /api/issues/{issue_id}`
- `GET /api/issues/{issue_id}/preview`
- `GET /api/daily-summaries/latest`
- `GET /api/delivery-logs`

## Use Cases

- 실시간 이슈 모니터링
- 주제별 뉴스 브리핑 자동화
- Slack 기반 내부 보고 자동화
- AI 요약을 활용한 정보 큐레이션

## Development Notes

- 브랜치는 기능 단위로 나누는 것을 권장합니다.
- 크롤링, 저장, 요약/전송, 런타임 로직은 역할별로 모듈 분리되어 있습니다.
- 백엔드 변경 경계는 [backend/README.md](backend/README.md)에 정리되어 있습니다.

## Testing

```bash
.venv/bin/pytest -q
npm run build
```

## Roadmap

- 소스별 파서 품질 보정
- X 실험 모듈 인증 정리
- Docker 기반 실행 환경 정리
- 프론트 컴포넌트 분리 고도화
