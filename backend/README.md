# FastAPI Backend

## Run

```bash
cd /home/muzy/testp/ai-issue-dashboard-vue
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

## Endpoints

- `GET /health`
- `GET /api/issues`
- `GET /api/issues/{issue_id}/preview`
- `GET /api/delivery-logs`

## Notes

- 현재는 프론트 화면과 맞춘 목업 데이터 기반 구현입니다.
- 이후 DB 연결 시 `repository.py` 부분만 SQLAlchemy 조회 로직으로 교체하면 됩니다.
