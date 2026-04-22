# Current DB Schema in dbdiagram

현재 실행 기준 스키마는 `backend/app/models.py`의 SQLAlchemy ORM을 따릅니다.
아래 문법은 `dbdiagram.io`에 바로 붙여 넣을 수 있는 DBML입니다.

```dbml
Table sources {
  id integer [pk]
  name varchar(100) [not null, unique]
  source_type varchar(30) [not null]
  base_url text
  is_active boolean [not null, default: true]
  created_at timestamptz [not null]
}

Table issues {
  id integer [pk]
  source_id integer [not null, ref: > sources.id]
  external_id varchar(255)
  press_name varchar(100)
  title varchar(500) [not null]
  original_url text
  category varchar(50) [not null, default: "뉴스"]
  region varchar(20)
  published_at timestamptz
  collected_at timestamptz [not null]
  raw_content text
  status varchar(30) [not null, default: "collected"]
  unique_hash varchar(64) [unique]
  created_at timestamptz [not null]
  updated_at timestamptz [not null]

  Indexes {
    source_id
    collected_at
    unique_hash
  }
}

Table issue_summaries {
  id integer [pk]
  issue_id integer [not null, ref: > issues.id]
  llm_provider varchar(50) [not null]
  llm_model varchar(100) [not null]
  prompt_version varchar(30)
  summary_text text [not null]
  importance varchar(20)
  key_points_json text
  research_value text
  tracking_keywords_json text
  summary_status varchar(30) [not null, default: "completed"]
  created_at timestamptz [not null]

  Indexes {
    issue_id
  }
}

Table issue_embeddings {
  id integer [pk]
  issue_id integer [not null, unique, ref: > issues.id]
  embedding_model varchar(100) [not null]
  content_hash varchar(64) [not null]
  embedding_json text [not null]
  created_at timestamptz [not null]
  updated_at timestamptz [not null]

  Indexes {
    issue_id
  }
}

Table report_channels {
  id integer [pk]
  name varchar(50) [not null, unique]
  channel_type varchar(30) [not null]
  destination varchar(255) [not null]
  is_active boolean [not null, default: true]
  created_at timestamptz [not null]
}

Table reports {
  id integer [pk]
  issue_id integer [not null, ref: > issues.id]
  summary_id integer [not null, ref: > issue_summaries.id]
  channel_id integer [not null, ref: > report_channels.id]
  report_title varchar(500) [not null]
  preview_message text [not null]
  report_status varchar(30) [not null, default: "ready"]
  created_at timestamptz [not null]

  Indexes {
    issue_id
    summary_id
    channel_id
  }
}

Table delivery_logs {
  id integer [pk]
  report_id integer [not null, ref: > reports.id]
  channel_id integer [not null, ref: > report_channels.id]
  delivery_status varchar(30) [not null]
  delivered_at timestamptz
  error_message text
  response_code varchar(30)
  response_body text
  retry_count integer [not null, default: 0]
  created_at timestamptz [not null]

  Indexes {
    report_id
    channel_id
    created_at
  }
}

Table daily_summaries {
  id integer [pk]
  summary_date varchar(10) [not null, unique]
  channel_id integer [not null, ref: > report_channels.id]
  status varchar(30) [not null, default: "ready"]
  message_text text [not null]
  payload_json text [not null]
  created_at timestamptz [not null]

  Indexes {
    summary_date
    channel_id
  }
}
```

참고:
- 이 문서는 현재 ORM 모델 기준입니다.
- `db/schema.sql`은 PostgreSQL 타깃 초안이라 현재 모델과 일부 차이가 있습니다.
- 현재 모델에는 `issue_keywords` 테이블이 없고, 대신 `issue_embeddings`와 `daily_summaries`가 포함됩니다.
