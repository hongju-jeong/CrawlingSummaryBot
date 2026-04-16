<script setup>
import { computed, onMounted, ref, watch } from "vue";

const issues = ref([]);
const logs = ref([]);
const selectedIssueId = ref(null);
const selectedPreview = ref(null);
const selectedIssueDetail = ref(null);
const isLoadingIssues = ref(false);
const isLoadingPreview = ref(false);
const isCrawling = ref(false);
const errorMessage = ref("");

const selectedIssue = computed(() => {
  return issues.value.find((issue) => issue.id === selectedIssueId.value) ?? null;
});

const selectedIssueBody = computed(() => {
  return selectedIssueDetail.value?.raw_content ?? "";
});

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

async function crawlLatestNews() {
  isCrawling.value = true;
  errorMessage.value = "";

  try {
    await requestJson("/api/crawl/naver-news/latest", {
      method: "POST",
      body: JSON.stringify({ limit: 5 }),
    });
    await loadIssues();
    await loadLogs();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isCrawling.value = false;
  }
}

function selectIssue(issueId) {
  selectedIssueId.value = issueId;
}

watch(selectedIssueId, (issueId) => {
  void loadPreview(issueId);
});

onMounted(async () => {
  await loadIssues();
  await loadLogs();
});
</script>

<template>
  <div class="page-shell compact">
    <header class="hero simple">
      <div>
        <p class="eyebrow">AI Monitor</p>
        <h1>실시간 이슈 자동 보고</h1>
        <p class="hero-copy">
          FastAPI에서 수집한 네이버 최신 뉴스 데이터를 그대로 불러옵니다. 이슈를 선택하면 자동 보고 미리보기와 원문을 확인할 수 있습니다.
        </p>
      </div>
      <div class="hero-actions">
        <button class="action-button" :disabled="isCrawling" @click="crawlLatestNews">
          {{ isCrawling ? "수집 중..." : "최신 뉴스 수집" }}
        </button>
        <div class="hero-status">
          <span class="status-dot"></span>
          <span>FastAPI 연동 활성화</span>
        </div>
      </div>
    </header>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>

    <main class="focused-grid">
      <section class="panel issue-list-panel">
        <div class="panel-header">
          <h2>실시간 이슈 리스트</h2>
          <span class="badge">{{ issues.length }}건</span>
        </div>

        <p v-if="isLoadingIssues" class="panel-state">이슈 목록을 불러오는 중입니다.</p>
        <p v-else-if="!issues.length" class="panel-state">
          아직 저장된 뉴스가 없습니다. 상단의 `최신 뉴스 수집` 버튼을 눌러주세요.
        </p>

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
            <p class="detail-summary">{{ selectedPreview.summary }}</p>
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

        <div v-for="log in logs" :key="log.id" class="log-row">
          <div>
            <strong>{{ log.title }}</strong>
            <p>{{ log.channel }} · {{ log.time }}</p>
          </div>
          <span
            class="badge"
            :class="{
              active: log.status === '성공',
              warning: log.status === '대기',
              danger: log.status === '실패',
            }"
          >
            {{ log.status }}
          </span>
        </div>
      </section>
    </main>
  </div>
</template>
