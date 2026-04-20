<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

const issues = ref([]);
const logs = ref([]);
const selectedIssueId = ref(null);
const selectedPreview = ref(null);
const selectedIssueDetail = ref(null);
const isLoadingIssues = ref(false);
const isLoadingPreview = ref(false);
const isCrawling = ref(false);
const errorMessage = ref("");
const runtimeProfile = ref(null);
const latestDailySummary = ref(null);
const activeTab = ref("monitoring");
const activeAbortController = ref(null);
const nowTick = ref(Date.now());
const lastAutoCrawlSnapshot = ref(null);
const monitoringSummary = ref({
  processCount: 0,
  sourceGroups: [],
  discoveredCount: 0,
  savedCount: 0,
  skippedCount: 0,
  failedCount: 0,
  sentCount: 0,
});
const liveItems = ref([]);
const activityFeed = ref([]);

const selectedIssue = computed(() => {
  return issues.value.find((issue) => issue.id === selectedIssueId.value) ?? null;
});

const selectedIssueBody = computed(() => {
  return selectedIssueDetail.value?.raw_content ?? "";
});

const recommendedProfileText = computed(() => {
  if (!runtimeProfile.value) return "";
  const profile = runtimeProfile.value.recommended;
  return `프로세스 ${profile.crawler_processes} · 프로세스당 동시성 ${profile.crawler_concurrency_per_process} · 호스트당 ${profile.crawler_host_concurrency} · 후처리 워커 ${profile.report_worker_threads}`;
});

const effectiveProfileText = computed(() => {
  if (!runtimeProfile.value) return "";
  const profile = runtimeProfile.value.effective;
  return `프로세스 ${profile.crawler_processes} · 프로세스당 동시성 ${profile.crawler_concurrency_per_process} · 호스트당 ${profile.crawler_host_concurrency} · 후처리 워커 ${profile.report_worker_threads}`;
});

const nextAutoCrawlCountdownText = computed(() => {
  if (!runtimeProfile.value?.scheduler_running) {
    return "자동 수집 비활성";
  }
  if (!runtimeProfile.value?.auto_crawl_armed) {
    return "첫 수동 수집 완료 후 자동 시작";
  }
  if (!runtimeProfile.value?.next_crawl_run_at) {
    return "다음 자동 수집 시간 계산 중";
  }
  const diffMs = new Date(runtimeProfile.value.next_crawl_run_at).getTime() - nowTick.value;
  if (diffMs <= 0) {
    return "곧 자동 수집 실행";
  }
  return formatDuration(diffMs);
});

const nextAutoCrawlLabel = computed(() => {
  if (!runtimeProfile.value?.scheduler_running) {
    return "자동 수집 비활성";
  }
  if (!runtimeProfile.value?.auto_crawl_armed) {
    return nextAutoCrawlCountdownText.value;
  }
  return `다음 자동 수집까지 ${nextAutoCrawlCountdownText.value}`;
});

const autoCrawlIntervalLabel = computed(() => {
  const minutes = runtimeProfile.value?.crawl_interval_minutes;
  if (!minutes || minutes <= 0) {
    return "자동 수집";
  }
  return `${minutes}분 주기 자동 수집`;
});

const dailySummaryTopics = computed(() => latestDailySummary.value?.payload?.topics ?? []);

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed: ${response.status}`);
  }

  return response.json();
}

async function loadIssues() {
  isLoadingIssues.value = true;
  errorMessage.value = "";

  try {
    const payload = await requestJson("/api/issues");
    issues.value = payload.items ?? [];

    if (!issues.value.length) {
      selectedIssueId.value = null;
      selectedPreview.value = null;
      selectedIssueDetail.value = null;
      return;
    }

    const currentExists = issues.value.some((issue) => issue.id === selectedIssueId.value);
    if (!currentExists) {
      selectedIssueId.value = issues.value[0].id;
    }
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isLoadingIssues.value = false;
  }
}

async function loadPreview(issueId) {
  if (!issueId) {
    selectedPreview.value = null;
    selectedIssueDetail.value = null;
    return;
  }

  isLoadingPreview.value = true;
  errorMessage.value = "";

  try {
    const [preview, detail] = await Promise.all([
      requestJson(`/api/issues/${issueId}/preview`),
      requestJson(`/api/issues/${issueId}`),
    ]);
    selectedPreview.value = preview;
    selectedIssueDetail.value = detail;
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isLoadingPreview.value = false;
  }
}

async function loadLogs() {
  try {
    const payload = await requestJson("/api/delivery-logs");
    logs.value = payload.items ?? [];
  } catch (error) {
    errorMessage.value = error.message;
  }
}

async function loadRuntimeProfile() {
  try {
    runtimeProfile.value = await requestJson("/api/runtime-profile");
    applyAutoCrawlRuntime(runtimeProfile.value);
  } catch (error) {
    errorMessage.value = error.message;
  }
}

async function loadLatestDailySummary() {
  try {
    latestDailySummary.value = await requestJson("/api/daily-summaries/latest");
  } catch (error) {
    latestDailySummary.value = null;
  }
}

function resetMonitoringState() {
  monitoringSummary.value = {
    processCount: 0,
    sourceGroups: [],
    discoveredCount: 0,
    savedCount: 0,
    skippedCount: 0,
    failedCount: 0,
    sentCount: 0,
  };
  liveItems.value = [];
  activityFeed.value = [];
}

function applyAutoCrawlRuntime(runtime) {
  const snapshot = {
    active: runtime.auto_crawl_active,
    finishedAt: runtime.auto_crawl_last_finished_at,
    status: runtime.auto_crawl_last_status,
    collected: runtime.auto_crawl_last_collected_count,
    saved: runtime.auto_crawl_last_saved_count,
    skipped: runtime.auto_crawl_last_skipped_count,
    failed: runtime.auto_crawl_last_failed_count,
  };
  const previous = lastAutoCrawlSnapshot.value;

  if (runtime.auto_crawl_active && (!previous || !previous.active)) {
    monitoringSummary.value.processCount = runtime.effective.crawler_processes;
    pushActivity({
      type: "run_started",
      title: "자동 크롤링 실행",
      process_count: runtime.effective.crawler_processes,
      source_groups: monitoringSummary.value.sourceGroups,
    });
  }

  const justFinished = snapshot.finishedAt && (!previous || previous.finishedAt !== snapshot.finishedAt);
  if (justFinished) {
    monitoringSummary.value.discoveredCount = snapshot.collected;
    monitoringSummary.value.savedCount = snapshot.saved;
    monitoringSummary.value.skippedCount = snapshot.skipped;
    monitoringSummary.value.failedCount = snapshot.failed;
    pushActivity({
      type: snapshot.status === "failed" ? "run_failed" : "run_completed",
      title: "자동 크롤링 완료",
      saved_count: snapshot.saved,
      skipped_count: snapshot.skipped,
      failed_count: snapshot.failed,
    });
    void loadIssues();
    void loadLogs();
    void loadLatestDailySummary();
  }

  lastAutoCrawlSnapshot.value = snapshot;
}

function upsertLiveItem(event) {
  const identity = event.issue_id ?? event.url ?? `${event.source}-${event.title}`;
  if (!identity) {
    return;
  }

  const current = liveItems.value.find((item) => item.identity === identity);
  if (!current) {
    liveItems.value.unshift({
      identity,
      title: event.title ?? "제목 없음",
      source: event.source ?? "출처 미상",
      category: event.category ?? "-",
      stage: mapStageLabel(event.type),
      statusTone: mapStageTone(event.type),
      summary: event.summary ?? "",
    });
    return;
  }

  current.title = event.title ?? current.title;
  current.source = event.source ?? current.source;
  current.category = event.category ?? current.category;
  current.stage = mapStageLabel(event.type);
  current.statusTone = mapStageTone(event.type);
  if (event.summary) {
    current.summary = event.summary;
  }
}

function pushActivity(event) {
  activityFeed.value.unshift({
    id: `${Date.now()}-${Math.random()}`,
    stage: mapStageLabel(event.type),
    title: event.title ?? (event.type === "run_started" ? "크롤링 실행" : "이벤트"),
    meta: buildActivityMeta(event),
    tone: mapStageTone(event.type),
  });
  activityFeed.value = activityFeed.value.slice(0, 24);
}

function buildActivityMeta(event) {
  if (event.type === "run_started") {
    return `프로세스 ${event.process_count}개 · 그룹 ${event.source_groups.join(", ")}`;
  }
  if (event.type === "crawl_completed") {
    return `수집 후보 ${event.discovered_count}건`;
  }
  if (event.type === "run_completed") {
    return `저장 ${event.saved_count} · 전송대기 ${event.skipped_count} · 실패 ${event.failed_count}`;
  }
  if (event.type === "run_cancelled") {
    return `저장 ${event.saved_count ?? 0} · 중단 요청 적용`;
  }
  const parts = [];
  if (event.source) parts.push(event.source);
  if (event.category) parts.push(event.category);
  if (event.error) parts.push(event.error);
  return parts.join(" · ");
}

function mapStageLabel(type) {
  const mapping = {
    run_started: "크롤러 시작",
    crawl_completed: "수집 완료",
    item_started: "기사 처리 시작",
    item_saved: "DB 저장",
    summary_completed: "AI 요약 완료",
    delivery_started: "Slack 전송 시작",
    delivery_sent: "Slack 전송 완료",
    delivery_failed: "Slack 전송 실패",
    delivery_ready: "전송 준비",
    item_skipped: "중복 건너뜀",
    item_failed: "처리 실패",
    item_completed: "처리 완료",
    run_completed: "작업 완료",
    run_cancelled: "작업 중단",
    run_failed: "작업 실패",
  };
  return mapping[type] ?? type;
}

function mapStageTone(type) {
  if (["delivery_sent", "run_completed", "summary_completed"].includes(type)) return "active";
  if (["delivery_started", "item_started", "item_saved", "crawl_completed", "delivery_ready"].includes(type)) {
    return "warning";
  }
  if (["run_cancelled"].includes(type)) return "warning";
  if (["delivery_failed", "item_failed", "run_failed"].includes(type)) return "danger";
  return "subtle";
}

function applyStreamEvent(event) {
  if (event.process_count !== undefined) {
    monitoringSummary.value.processCount = event.process_count;
  }
  if (event.source_groups) {
    monitoringSummary.value.sourceGroups = event.source_groups;
  }
  if (event.discovered_count !== undefined) {
    monitoringSummary.value.discoveredCount = event.discovered_count;
  }
  if (event.saved_count !== undefined) {
    monitoringSummary.value.savedCount = event.saved_count;
  }
  if (event.skipped_count !== undefined) {
    monitoringSummary.value.skippedCount = event.skipped_count;
  }
  if (event.failed_count !== undefined) {
    monitoringSummary.value.failedCount = event.failed_count;
  }
  if (event.type === "delivery_sent") {
    monitoringSummary.value.sentCount += 1;
  }

  if (event.title || event.issue_id || event.url) {
    upsertLiveItem(event);
  }
  pushActivity(event);
}

async function crawlLatestNews() {
  if (isCrawling.value) {
    await stopLatestNews();
    return;
  }

  isCrawling.value = true;
  errorMessage.value = "";
  resetMonitoringState();
  const controller = new AbortController();
  activeAbortController.value = controller;

  try {
    const response = await fetch("/api/crawl/latest/stream?limit=5", {
      signal: controller.signal,
    });
    if (!response.ok || !response.body) {
      throw new Error(`Stream failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        applyStreamEvent(event);
      }
    }

    if (buffer.trim()) {
      applyStreamEvent(JSON.parse(buffer));
    }

    await loadIssues();
    await loadLogs();
    await loadLatestDailySummary();
    await loadRuntimeProfile();
  } catch (error) {
    if (error.name !== "AbortError") {
      errorMessage.value = error.message;
    }
  } finally {
    activeAbortController.value = null;
    isCrawling.value = false;
    await loadRuntimeProfile();
  }
}

async function stopLatestNews() {
  try {
    await requestJson("/api/crawl/latest/stop", { method: "POST" });
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    activeAbortController.value?.abort();
    await loadRuntimeProfile();
  }
}

function formatDuration(durationMs) {
  const totalSeconds = Math.max(Math.floor(durationMs / 1000), 0);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

let countdownTimer = null;
let autoRefreshTimer = null;

function selectIssue(issueId) {
  selectedIssueId.value = issueId;
}

watch(selectedIssueId, (issueId) => {
  void loadPreview(issueId);
});

onMounted(async () => {
  await loadRuntimeProfile();
  await loadIssues();
  await loadLogs();
  await loadLatestDailySummary();
  countdownTimer = window.setInterval(() => {
    nowTick.value = Date.now();
  }, 1000);
  autoRefreshTimer = window.setInterval(() => {
    if (!isCrawling.value) {
      void loadRuntimeProfile();
    }
  }, 5000);
});

onUnmounted(() => {
  if (countdownTimer) {
    window.clearInterval(countdownTimer);
  }
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer);
  }
});
</script>

<template>
  <div class="page-shell compact dashboard-shell">
    <div class="workspace-shell">
      <aside class="tab-sidebar panel">
        <p class="eyebrow">AI Monitor</p>
        <h1 class="sidebar-title">뉴스 분석 워크스페이스</h1>
        <p class="sidebar-copy">실시간 모니터링과 전날 요약을 탭으로 나눠서 확인합니다.</p>
        <div class="tab-nav">
          <button class="tab-button" :class="{ active: activeTab === 'monitoring' }" @click="activeTab = 'monitoring'">
            <span class="tab-button-title">모니터링</span>
            <span class="tab-button-copy">실시간 수집, 처리 현황, 전송 로그</span>
          </button>
          <button class="tab-button" :class="{ active: activeTab === 'daily-summary' }" @click="activeTab = 'daily-summary'">
            <span class="tab-button-title">전날 요약</span>
            <span class="tab-button-copy">최근 daily digest와 토픽별 키워드 요약</span>
          </button>
        </div>
      </aside>

      <section class="tab-content">
        <template v-if="activeTab === 'monitoring'">
          <header class="hero simple">
            <div>
              <p class="eyebrow">Realtime View</p>
              <h1>실시간 이슈 모니터링 대시보드</h1>
              <p class="hero-copy">
                수집 버튼을 누르면 크롤링 프로세스 수, 기사별 AI 요약, Slack 전송 단계를 실시간으로 추적합니다.
              </p>
              <div v-if="runtimeProfile" class="runtime-strip">
                <span class="badge warning">{{ autoCrawlIntervalLabel }}</span>
                <span class="badge warning profile-badge">{{ nextAutoCrawlLabel }}</span>
                <span class="badge subtle">
                  시스템
                  {{ runtimeProfile.system.physical_cores }}C /
                  {{ runtimeProfile.system.logical_cores }}T
                  <template v-if="runtimeProfile.system.memory_gb">
                    · {{ runtimeProfile.system.memory_gb }}GB RAM
                  </template>
                </span>
                <span class="badge subtle profile-badge">추천 · {{ recommendedProfileText }}</span>
                <span class="badge active profile-badge">적용 · {{ effectiveProfileText }}</span>
                <span v-if="latestDailySummary" class="badge subtle profile-badge">
                  최근 일일 요약 · {{ latestDailySummary.summary_date }} · {{ latestDailySummary.status }}
                </span>
              </div>
            </div>
            <div class="hero-actions">
              <button class="action-button" @click="crawlLatestNews">
                {{ isCrawling ? "최신 뉴스 수집 중단" : "최신 뉴스 수집" }}
              </button>
              <div class="hero-status">
                <span class="status-dot"></span>
                <span>
                  {{
                    isCrawling
                      ? "실시간 스트리밍 활성화"
                      : runtimeProfile?.auto_crawl_active
                        ? "자동 크롤링 실행 중"
                        : "대기 중"
                  }}
                </span>
              </div>
            </div>
          </header>

          <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>

          <section class="monitor-grid">
            <article class="panel stat-card">
              <span class="detail-label">크롤링 프로세스</span>
              <strong>{{ monitoringSummary.processCount }}</strong>
              <p>{{ monitoringSummary.sourceGroups.join(", ") || "대기 중" }}</p>
            </article>
            <article class="panel stat-card">
              <span class="detail-label">수집 후보</span>
              <strong>{{ monitoringSummary.discoveredCount }}</strong>
              <p>실시간 발견 기사 수</p>
            </article>
            <article class="panel stat-card">
              <span class="detail-label">저장 완료</span>
              <strong>{{ monitoringSummary.savedCount }}</strong>
              <p>DB 적재 완료 건수</p>
            </article>
            <article class="panel stat-card">
              <span class="detail-label">Slack 전송 완료</span>
              <strong>{{ monitoringSummary.sentCount }}</strong>
              <p>실시간 전송 성공 건수</p>
            </article>
          </section>

          <main class="dashboard-grid">
            <section class="panel live-panel">
              <div class="panel-header">
                <h2>실시간 처리 현황</h2>
                <span class="badge warning">{{ liveItems.length }}건 추적 중</span>
              </div>

              <p v-if="!liveItems.length" class="panel-state">
                최신 뉴스 수집을 실행하면 기사별 처리 단계가 실시간으로 쌓입니다.
              </p>

              <div v-else class="panel-scroll panel-scroll-tall">
                <div v-for="item in liveItems" :key="item.identity" class="live-item">
                  <div class="issue-row-top">
                    <span class="badge subtle">{{ item.category }}</span>
                    <span class="badge" :class="item.statusTone">{{ item.stage }}</span>
                  </div>
                  <h3>{{ item.title }}</h3>
                  <p>{{ item.source }}</p>
                  <p v-if="item.summary" class="live-summary">{{ item.summary }}</p>
                </div>
              </div>
            </section>

            <section class="panel activity-panel">
              <div class="panel-header">
                <h2>실시간 이벤트 피드</h2>
                <span class="badge">{{ activityFeed.length }}개</span>
              </div>

              <p v-if="!activityFeed.length" class="panel-state">아직 스트리밍 이벤트가 없습니다.</p>

              <div v-else class="panel-scroll">
                <div v-for="event in activityFeed" :key="event.id" class="activity-row">
                  <span class="badge" :class="event.tone">{{ event.stage }}</span>
                  <div>
                    <strong>{{ event.title }}</strong>
                    <p>{{ event.meta }}</p>
                  </div>
                </div>
              </div>
            </section>

            <section class="panel issue-list-panel">
              <div class="panel-header">
                <h2>실시간 이슈 리스트</h2>
                <span class="badge">{{ issues.length }}건</span>
              </div>

              <p v-if="isLoadingIssues" class="panel-state">이슈 목록을 불러오는 중입니다.</p>
              <p v-else-if="!issues.length" class="panel-state">
                아직 저장된 뉴스가 없습니다. 상단의 `최신 뉴스 수집` 버튼을 눌러주세요.
              </p>

              <div v-else class="panel-scroll panel-scroll-tall">
                <div
                  v-for="issue in issues"
                  :key="issue.id"
                  class="issue-row"
                  :class="{ selected: issue.id === selectedIssue?.id }"
                  @click="selectIssue(issue.id)"
                >
                  <div class="issue-row-top">
                    <span class="badge subtle">{{ issue.category }}</span>
                    <span class="issue-time">{{ issue.time }}</span>
                  </div>
                  <h3>{{ issue.title }}</h3>
                  <p>{{ issue.source }}</p>
                  <div class="issue-meta">
                    <span>{{ issue.report_status }}</span>
                  </div>
                </div>
              </div>
            </section>

            <section class="panel preview-panel">
              <div class="panel-header">
                <h2>자동 보고 미리보기</h2>
                <span class="badge active">AI 요약 + Slack</span>
              </div>

              <p v-if="isLoadingPreview" class="panel-state">선택한 이슈를 불러오는 중입니다.</p>
              <p v-else-if="!selectedPreview" class="panel-state">
                왼쪽에서 이슈를 선택하면 자동 보고 미리보기가 표시됩니다.
              </p>

              <div v-else class="preview-card">
                <p class="preview-channel">{{ selectedPreview.destination }}</p>
                <h3 class="detail-title">{{ selectedPreview.title }}</h3>
                <div class="summary-box">
                  <div class="panel-header compact">
                    <h2>AI 요약</h2>
                    <span class="badge subtle">gpt-5.4-mini</span>
                  </div>
                  <p class="preview-channel">주제 · {{ selectedPreview.category }}</p>
                  <p v-if="selectedPreview.importance" class="preview-channel">중요도 · {{ selectedPreview.importance }}</p>
                  <p class="detail-summary">{{ selectedPreview.summary }}</p>
                  <div v-if="selectedPreview.key_points?.length" class="detail-grid single analysis-list">
                    <div>
                      <span class="detail-label">핵심 포인트</span>
                      <ul>
                        <li v-for="point in selectedPreview.key_points" :key="point">{{ point }}</li>
                      </ul>
                    </div>
                  </div>
                  <div v-if="selectedPreview.research_value" class="detail-grid single">
                    <div>
                      <span class="detail-label">리서치 포인트</span>
                      <strong>{{ selectedPreview.research_value }}</strong>
                    </div>
                  </div>
                  <div v-if="selectedPreview.tracking_keywords?.length" class="detail-grid single">
                    <div>
                      <span class="detail-label">추적 키워드</span>
                      <strong>{{ selectedPreview.tracking_keywords.join(', ') }}</strong>
                    </div>
                  </div>
                </div>

                <div class="detail-grid single">
                  <div>
                    <span class="detail-label">출처</span>
                    <strong>{{ selectedPreview.source }}</strong>
                  </div>
                </div>

                <div class="article-body">
                  <div class="panel-header compact">
                    <h2>기사 원문</h2>
                    <span class="badge subtle">DB 저장값</span>
                  </div>
                  <p>{{ selectedIssueBody }}</p>
                </div>
              </div>
            </section>

            <section class="panel log-panel">
              <div class="panel-header">
                <h2>채널 전송 로그</h2>
                <span class="badge subtle">{{ logs.length }}건</span>
              </div>

              <p v-if="!logs.length" class="panel-state">아직 저장된 채널 전송 로그가 없습니다.</p>

              <div v-else class="panel-scroll panel-scroll-tall">
                <div v-for="log in logs" :key="log.id" class="log-row">
                  <div>
                    <strong>{{ log.title }}</strong>
                    <p>{{ log.category }} · {{ log.channel }} · {{ log.time }}</p>
                  </div>
                  <span
                    class="badge"
                    :class="{
                      active: log.status === '성공',
                      warning: log.status === '대기' || log.status === '중단',
                      danger: log.status === '실패',
                    }"
                  >
                    {{ log.status }}
                  </span>
                </div>
              </div>
            </section>
          </main>
        </template>

        <template v-else>
          <header class="hero simple">
            <div>
              <p class="eyebrow">Daily Digest</p>
              <h1>전날 요약 기사</h1>
              <p class="hero-copy">
                자정 기준으로 생성된 최신 daily digest를 토픽별 키워드와 설명, 대표 기사 링크 중심으로 확인합니다.
              </p>
            </div>
          </header>

          <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>

          <section class="daily-summary-layout">
            <article class="panel daily-summary-hero">
              <div class="panel-header">
                <h2>최근 일일 요약 상태</h2>
                <span v-if="latestDailySummary" class="badge active">{{ latestDailySummary.status }}</span>
              </div>
              <p v-if="!latestDailySummary" class="panel-state">아직 생성된 daily digest가 없습니다.</p>
              <template v-else>
                <div class="detail-grid">
                  <div>
                    <span class="detail-label">요약 날짜</span>
                    <p>{{ latestDailySummary.summary_date }}</p>
                  </div>
                  <div>
                    <span class="detail-label">전송 채널</span>
                    <p>{{ latestDailySummary.channel }}</p>
                  </div>
                </div>
                <div class="summary-box">
                  <span class="detail-label">저장된 메시지</span>
                  <div class="slack-message">
                    <p>{{ latestDailySummary.message_text }}</p>
                  </div>
                </div>
              </template>
            </article>

            <article class="panel daily-summary-topics">
              <div class="panel-header">
                <h2>토픽별 키워드 요약</h2>
                <span class="badge">{{ dailySummaryTopics.length }}개 토픽</span>
              </div>

              <p v-if="!dailySummaryTopics.length" class="panel-state">표시할 전날 요약 토픽이 없습니다.</p>

              <div v-else class="daily-topic-grid">
                <section v-for="topic in dailySummaryTopics" :key="topic.topic" class="daily-topic-card">
                  <div class="panel-header compact">
                    <h3>{{ topic.topic }}</h3>
                    <span class="badge subtle">{{ topic.keywords?.length ?? 0 }}개 키워드</span>
                  </div>
                  <div class="daily-keyword-list">
                    <article
                      v-for="keyword in topic.keywords"
                      :key="`${topic.topic}-${keyword.keyword}`"
                      class="daily-keyword-row"
                    >
                      <div class="issue-row-top">
                        <span class="chip strong">{{ keyword.keyword }}</span>
                      </div>
                      <p class="daily-keyword-description">{{ keyword.description }}</p>
                      <a
                        v-if="keyword.representative_article_url"
                        class="daily-keyword-link"
                        :href="keyword.representative_article_url"
                        target="_blank"
                        rel="noreferrer"
                      >
                        대표 기사 보기
                      </a>
                    </article>
                  </div>
                </section>
              </div>
            </article>
          </section>
        </template>
      </section>
    </div>
  </div>
</template>
