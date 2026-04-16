-- AI issue monitoring prototype schema
-- Target DB: PostgreSQL

create table sources (
  id bigserial primary key,
  name varchar(100) not null,
  source_type varchar(30) not null,
  base_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create unique index uq_sources_name on sources(name);


create table issues (
  id bigserial primary key,
  source_id bigint not null references sources(id),
  external_id varchar(255),
  title varchar(500) not null,
  original_url text,
  category varchar(50) not null,
  region varchar(20),
  published_at timestamptz,
  collected_at timestamptz not null default now(),
  raw_content text,
  status varchar(30) not null default 'collected',
  unique_hash varchar(64),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index uq_issues_unique_hash on issues(unique_hash);
create index idx_issues_collected_at on issues(collected_at desc);
create index idx_issues_category on issues(category);
create index idx_issues_status on issues(status);


create table issue_keywords (
  id bigserial primary key,
  issue_id bigint not null references issues(id) on delete cascade,
  keyword varchar(100) not null,
  created_at timestamptz not null default now()
);

create index idx_issue_keywords_issue_id on issue_keywords(issue_id);
create index idx_issue_keywords_keyword on issue_keywords(keyword);


create table issue_summaries (
  id bigserial primary key,
  issue_id bigint not null references issues(id) on delete cascade,
  llm_provider varchar(50) not null,
  llm_model varchar(100) not null,
  prompt_version varchar(30),
  summary_text text not null,
  summary_status varchar(30) not null default 'completed',
  created_at timestamptz not null default now()
);

create index idx_issue_summaries_issue_id on issue_summaries(issue_id);
create index idx_issue_summaries_created_at on issue_summaries(created_at desc);


create table report_channels (
  id bigserial primary key,
  name varchar(50) not null,
  channel_type varchar(30) not null,
  destination varchar(255) not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create unique index uq_report_channels_name on report_channels(name);


create table reports (
  id bigserial primary key,
  issue_id bigint not null references issues(id) on delete cascade,
  summary_id bigint not null references issue_summaries(id) on delete cascade,
  channel_id bigint not null references report_channels(id),
  report_title varchar(500) not null,
  preview_message text not null,
  report_status varchar(30) not null default 'ready',
  created_at timestamptz not null default now()
);

create index idx_reports_issue_id on reports(issue_id);
create index idx_reports_channel_id on reports(channel_id);
create index idx_reports_status on reports(report_status);


create table delivery_logs (
  id bigserial primary key,
  report_id bigint not null references reports(id) on delete cascade,
  channel_id bigint not null references report_channels(id),
  delivery_status varchar(30) not null,
  delivered_at timestamptz,
  error_message text,
  response_code varchar(30),
  response_body text,
  retry_count integer not null default 0,
  created_at timestamptz not null default now()
);

create index idx_delivery_logs_report_id on delivery_logs(report_id);
create index idx_delivery_logs_channel_id on delivery_logs(channel_id);
create index idx_delivery_logs_created_at on delivery_logs(created_at desc);


-- Sample mapping to the current UI
-- 1. 실시간 이슈 리스트
--    issues + sources
--
-- 2. 자동 보고 미리보기
--    issues + issue_summaries + reports + report_channels
--
-- 3. 채널 전송 로그
--    delivery_logs + reports + report_channels
