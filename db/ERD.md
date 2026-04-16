# ERD Summary

FastAPI 백엔드 기준으로 현재 화면에 필요한 데이터 구조를 ERD 형태의 표로 정리한 문서입니다.

## 1. `sources`

| 항목 | 내용 |
|---|---|
| 설명 | 이슈를 수집하는 외부 데이터 출처 |
| PK | `id` |
| 주요 컬럼 | `name`, `source_type`, `base_url`, `is_active`, `created_at` |
| 참조 관계 | `issues.source_id` 가 `sources.id` 참조 |

## 2. `issues`

| 항목 | 내용 |
|---|---|
| 설명 | 수집된 실시간 이슈 원본 데이터 |
| PK | `id` |
| FK | `source_id -> sources.id` |
| 주요 컬럼 | `external_id`, `press_name`, `title`, `original_url`, `category`, `region`, `published_at`, `collected_at`, `raw_content`, `status`, `unique_hash` |
| 화면 연결 | 실시간 이슈 리스트 |

## 3. `issue_keywords`

| 항목 | 내용 |
|---|---|
| 설명 | 이슈별 키워드 저장 |
| PK | `id` |
| FK | `issue_id -> issues.id` |
| 주요 컬럼 | `keyword`, `created_at` |
| 참조 관계 | 하나의 이슈에 여러 키워드 연결 가능 |

## 4. `issue_summaries`

| 항목 | 내용 |
|---|---|
| 설명 | LLM이 생성한 이슈 요약 결과 |
| PK | `id` |
| FK | `issue_id -> issues.id` |
| 주요 컬럼 | `llm_provider`, `llm_model`, `prompt_version`, `summary_text`, `summary_status`, `created_at` |
| 화면 연결 | 자동 보고 미리보기 |

## 5. `report_channels`

| 항목 | 내용 |
|---|---|
| 설명 | Slack, 이메일 등 자동 보고 대상 채널 |
| PK | `id` |
| 주요 컬럼 | `name`, `channel_type`, `destination`, `is_active`, `created_at` |
| 참조 관계 | `reports.channel_id`, `delivery_logs.channel_id` 가 참조 |

## 6. `reports`

| 항목 | 내용 |
|---|---|
| 설명 | 이슈와 LLM 요약을 바탕으로 생성된 보고 메시지 |
| PK | `id` |
| FK | `issue_id -> issues.id`, `summary_id -> issue_summaries.id`, `channel_id -> report_channels.id` |
| 주요 컬럼 | `report_title`, `preview_message`, `report_status`, `created_at` |
| 화면 연결 | 자동 보고 미리보기 |

## 7. `delivery_logs`

| 항목 | 내용 |
|---|---|
| 설명 | 채널 전송 이력 및 성공/실패 로그 |
| PK | `id` |
| FK | `report_id -> reports.id`, `channel_id -> report_channels.id` |
| 주요 컬럼 | `delivery_status`, `delivered_at`, `error_message`, `response_code`, `response_body`, `retry_count`, `created_at` |
| 화면 연결 | 채널 전송 로그 |

## 관계 요약

| 부모 테이블 | 자식 테이블 | 관계 |
|---|---|---|
| `sources` | `issues` | 1:N |
| `issues` | `issue_keywords` | 1:N |
| `issues` | `issue_summaries` | 1:N |
| `issues` | `reports` | 1:N |
| `issue_summaries` | `reports` | 1:N |
| `report_channels` | `reports` | 1:N |
| `reports` | `delivery_logs` | 1:N |
| `report_channels` | `delivery_logs` | 1:N |

## 화면 기준 데이터 흐름

| 화면 기능 | 사용하는 테이블 |
|---|---|
| 실시간 이슈 리스트 | `issues`, `sources` |
| 자동 보고 미리보기 | `issues`, `issue_summaries`, `reports`, `report_channels` |
| 채널 전송 로그 | `delivery_logs`, `reports`, `report_channels` |

## FastAPI 구현 관점

| 계층 | 추천 매핑 |
|---|---|
| SQLAlchemy Model | 테이블별로 1개씩 생성 |
| Pydantic Schema | `IssueListResponse`, `ReportPreviewResponse`, `DeliveryLogResponse` 등으로 분리 |
| API Router | `/issues`, `/reports/preview/{issue_id}`, `/delivery-logs` |
| Service Layer | `issue_service`, `summary_service`, `report_service`, `delivery_service` |

## 간단한 ERD 텍스트 표현

```text
sources 1 --- N issues
issues 1 --- N issue_keywords
issues 1 --- N issue_summaries
issues 1 --- N reports
issue_summaries 1 --- N reports
report_channels 1 --- N reports
reports 1 --- N delivery_logs
report_channels 1 --- N delivery_logs
```
