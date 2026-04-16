<script setup>
import { computed, ref } from "vue";

const issues = ref([
  {
    id: 1,
    title: "미국 기준금리 동결 가능성 확대, 글로벌 증시 변동성 증가",
    source: "Reuters API",
    category: "금융",
    time: "3분 전",
    impact: 91,
    summary:
      "미 연준 관련 발언과 물가 지표가 혼재되며 금리 동결 전망이 우세해졌고, 기술주 중심으로 단기 변동성이 확대되고 있습니다.",
    keywords: ["금리", "연준", "미국증시", "인플레이션"],
    reportChannel: "Slack",
    reportStatus: "전송 완료",
  },
  {
    id: 2,
    title: "국내 반도체 수출 회복세, 공급망 리스크는 여전",
    source: "NewsAPI",
    category: "산업",
    time: "12분 전",
    impact: 84,
    summary:
      "반도체 수출이 회복 흐름을 보이고 있으나 원자재 가격과 특정 국가 규제 이슈가 동시에 부각되며 공급망 불확실성은 남아 있습니다.",
    keywords: ["반도체", "수출", "공급망", "산업통상"],
    reportChannel: "Slack",
    reportStatus: "전송 대기",
  },
  {
    id: 3,
    title: "유럽 AI 규제 후속안 발표 임박, 플랫폼 기업 대응 강화",
    source: "SerpAPI",
    category: "정책",
    time: "25분 전",
    impact: 76,
    summary:
      "유럽 규제기관의 후속 가이드라인 발표가 예고되면서 주요 플랫폼 기업들이 모델 투명성과 데이터 거버넌스 대응안을 조정하고 있습니다.",
    keywords: ["AI 규제", "EU", "플랫폼", "정책"],
    reportChannel: "Slack",
    reportStatus: "생성 완료",
  },
]);

const logs = ref([
  {
    id: 1,
    title: "미국 기준금리 동결 가능성 확대",
    channel: "Slack",
    time: "09:41",
    status: "성공",
  },
  {
    id: 2,
    title: "국내 반도체 수출 회복세",
    channel: "Slack",
    time: "09:35",
    status: "대기",
  },
  {
    id: 3,
    title: "유럽 AI 규제 후속안 발표 임박",
    channel: "Slack",
    time: "09:12",
    status: "실패",
  },
]);

const selectedIssueId = ref(1);

const selectedIssue = computed(() => {
  return issues.value.find((issue) => issue.id === selectedIssueId.value) ?? issues.value[0];
});

function selectIssue(issueId) {
  selectedIssueId.value = issueId;
}
</script>

<template>
  <div class="page-shell compact">
    <header class="hero simple">
      <div>
        <p class="eyebrow">AI Monitor</p>
        <h1>실시간 이슈 자동 보고</h1>
        <p class="hero-copy">
          필요한 기능만 남긴 화면입니다. 이슈를 선택하면 LLM 요약 기반 Slack 보고 미리보기를 바로 확인할 수 있습니다.
        </p>
      </div>
      <div class="hero-status">
        <span class="status-dot"></span>
        <span>Slack 자동 보고 활성화</span>
      </div>
    </header>

    <main class="focused-grid">
      <section class="panel issue-list-panel">
        <div class="panel-header">
          <h2>실시간 이슈 리스트</h2>
          <span class="badge">{{ issues.length }}건</span>
        </div>

        <div
          v-for="issue in issues"
          :key="issue.id"
          class="issue-row"
          :class="{ selected: issue.id === selectedIssue.id }"
          @click="selectIssue(issue.id)"
        >
          <div class="issue-row-top">
            <span class="badge subtle">{{ issue.category }}</span>
            <span class="issue-time">{{ issue.time }}</span>
          </div>
          <h3>{{ issue.title }}</h3>
          <p>{{ issue.source }}</p>
          <div class="issue-meta">
            <span>{{ issue.reportStatus }}</span>
          </div>
        </div>
      </section>

      <section class="panel preview-panel">
        <div class="panel-header">
          <h2>자동 보고 미리보기</h2>
          <span class="badge active">Slack</span>
        </div>

        <div class="preview-card">
          <p class="preview-channel"># exec-briefing</p>
          <h3 class="detail-title">{{ selectedIssue.title }}</h3>
          <p class="detail-summary">{{ selectedIssue.summary }}</p>

          <div class="detail-grid single">
            <div>
              <span class="detail-label">출처</span>
              <strong>{{ selectedIssue.source }}</strong>
            </div>
          </div>

          <div class="slack-message">
            <p>*[긴급 이슈 브리핑]* {{ selectedIssue.title }}</p>
            <p>요약: {{ selectedIssue.summary }}</p>
          </div>
        </div>
      </section>

      <section class="panel log-panel">
        <div class="panel-header">
          <h2>채널 전송 로그</h2>
          <span class="badge subtle">최근 3건</span>
        </div>

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
