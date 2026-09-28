<script setup>
import { computed, onMounted, ref } from "vue";

const session = ref(null);
const overview = ref(null);
const username = ref("");
const password = ref("");
const busy = ref(false);
const error = ref("");
const activeRegion = ref(null);

const hotspots = computed(() => overview.value?.regions ?? []);
const highestRisk = computed(
  () => hotspots.value.filter((item) => item.risk_pct >= 60).length,
);
const selectedRegion = computed(
  () =>
    hotspots.value.find((item) => item.region_key === activeRegion.value) ??
    hotspots.value[0],
);

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(body.detail || `伺服器回應 ${response.status}`);
  return body;
}

async function refresh() {
  busy.value = true;
  error.value = "";
  try {
    overview.value = await request("/api/overview");
    if (
      !activeRegion.value ||
      !overview.value.regions.some(
        (item) => item.region_key === activeRegion.value,
      )
    ) {
      activeRegion.value = overview.value.regions[0]?.region_key ?? null;
    }
  } catch (reason) {
    error.value = reason.message;
    if (reason.message === "請先登入") session.value = null;
  } finally {
    busy.value = false;
  }
}

async function login() {
  busy.value = true;
  error.value = "";
  try {
    session.value = await request("/api/session", {
      method: "POST",
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    });
    password.value = "";
    await refresh();
  } catch (reason) {
    error.value = reason.message;
  } finally {
    busy.value = false;
  }
}

async function logout() {
  await request("/api/session", { method: "DELETE" }).catch(() => {});
  session.value = null;
  overview.value = null;
  password.value = "";
  error.value = "";
}

function markerPosition(item) {
  return {
    left: `${Math.max(2, Math.min(98, ((item.longitude + 180) / 360) * 100))}%`,
    top: `${Math.max(4, Math.min(96, ((90 - item.latitude) / 180) * 100))}%`,
  };
}

function riskBand(value) {
  if (value >= 60) return "high";
  if (value >= 35) return "medium";
  return "low";
}

function formatDate(value) {
  if (!value) return "尚無更新時間";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("zh-TW");
}

onMounted(async () => {
  try {
    session.value = await request("/api/session");
    await refresh();
  } catch {
    session.value = null;
  }
});
</script>

<template>
  <div v-if="!session" class="login-shell">
    <div class="login-intro">
      <div class="brand-mark">N<span>·</span>R</div>
      <p class="eyebrow">INVENTORY INTELLIGENCE / VUE EDITION</p>
      <h1>從風險訊號，<br /><em>看見下一步。</em></h1>
      <p>將供應鏈風險、供應商據點與 ERP 資料放在同一個視野。</p>
      <div class="intro-foot">個人作業版 · Vue 前端 × Python API</div>
    </div>
    <main class="login-panel">
      <form class="login-card" @submit.prevent="login">
        <span class="panel-label">安全存取</span>
        <h2>登入風險中心</h2>
        <p>使用本作業版獨立資料庫的示範帳號。</p>
        <label for="username">使用者帳號</label>
        <input
          id="username"
          v-model="username"
          autocomplete="username"
          required
          placeholder="例如 viewer"
        />
        <label for="password">密碼</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          placeholder="輸入密碼"
        />
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <button class="primary-button" :disabled="busy" type="submit">
          {{ busy ? "登入中…" : "進入系統 →" }}
        </button>
        <div class="demo-note">本機展示帳號：<code>viewer / viewer</code></div>
      </form>
    </main>
  </div>

  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand-mark compact">N<span>·</span>R</div>
      <div class="sidebar-divider"></div>
      <span class="side-caption">工作區</span>
      <div class="side-active">
        <span class="side-icon">◈</span> 供應鏈風險總覽
      </div>
      <div class="sidebar-bottom">
        <div class="sidebar-person">
          <span class="avatar">{{ session.name?.slice(0, 1) }}</span
          ><span
            ><strong>{{ session.name }}</strong
            ><small>{{ session.role }}</small></span
          >
        </div>
        <button class="side-logout" @click="logout">登出 ↗</button>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <span>供應鏈風險中心 <span class="crumb">/ 風險總覽</span></span
        ><span class="environment-badge"><i></i> 獨立作業版</span>
      </header>
      <div class="workspace-content">
        <section class="page-heading">
          <div>
            <div class="eyebrow dark">SUPPLY CHAIN OVERVIEW</div>
            <h1>掌握風險，<span>提早應對。</span></h1>
            <p>依 ERP 已登錄的供應商與事件資料，檢視目前的供應鏈曝險。</p>
          </div>
          <button class="refresh-button" :disabled="busy" @click="refresh">
            {{ busy ? "載入中…" : "↻ 更新資料" }}
          </button>
        </section>

        <p v-if="error" class="alert" role="alert">{{ error }}</p>
        <template v-if="overview">
          <div class="data-time">
            資料查詢時間：{{
              formatDate(overview.generated_at)
            }}　·　風險數字來自 ERP 現有事件與供應商據點
          </div>
          <section class="metric-grid" aria-label="供應鏈風險指標">
            <article class="metric-card">
              <span>近 30 天風險事件</span>
              <div class="metric-value">
                {{ overview.kpis.event_count }}<small>宗</small>
              </div>
              <p>ERP 已登錄的異常事件</p>
            </article>
            <article class="metric-card">
              <span>受波及供應商</span>
              <div class="metric-value">
                {{ overview.kpis.supplier_count }}<small>家</small>
              </div>
              <p>與事件地區相關的供應商</p>
            </article>
            <article class="metric-card">
              <span>可能受波及訂單</span>
              <div class="metric-value">
                {{ overview.kpis.order_count }}<small>筆</small>
              </div>
              <p>需進一步檢查交期的訂單</p>
            </article>
            <article class="metric-card emphasized">
              <span>高風險據點</span>
              <div class="metric-value">{{ highestRisk }}<small>處</small></div>
              <p>地區風險分數達 60% 以上</p>
            </article>
          </section>

          <section class="main-grid">
            <article class="surface map-surface">
              <div class="section-title">
                <div>
                  <div class="eyebrow dark">GEOGRAPHIC EXPOSURE</div>
                  <h2>供應鏈風險據點</h2>
                </div>
                <span class="section-count">{{ hotspots.length }} 個地點</span>
              </div>
              <div
                class="world-grid"
                aria-label="依經緯度呈現的供應商風險據點示意圖"
              >
                <div class="map-label america">美洲</div>
                <div class="map-label europe">歐洲</div>
                <div class="map-label asia">亞洲</div>
                <button
                  v-for="region in hotspots"
                  :key="region.region_key"
                  class="map-pin"
                  :class="[
                    riskBand(region.risk_pct),
                    { selected: activeRegion === region.region_key },
                  ]"
                  :style="markerPosition(region)"
                  :title="`${region.display_name} · ${region.risk_pct}%`"
                  :aria-label="`${region.display_name}，風險 ${region.risk_pct}%`"
                  @click="activeRegion = region.region_key"
                ></button>
                <div v-if="!hotspots.length" class="empty-map">
                  目前沒有可顯示的供應商據點
                </div>
              </div>
              <div class="map-footer">
                <span><i class="legend low"></i> 低</span
                ><span><i class="legend medium"></i> 中</span
                ><span><i class="legend high"></i> 高</span
                ><small>點選據點查看詳情</small>
              </div>
            </article>

            <article class="surface region-surface">
              <div class="section-title">
                <div>
                  <div class="eyebrow dark">LOCATION DETAIL</div>
                  <h2>據點詳情</h2>
                </div>
              </div>
              <template v-if="selectedRegion">
                <div
                  class="risk-ring"
                  :class="riskBand(selectedRegion.risk_pct)"
                  :style="{
                    '--risk-fill': `${Math.max(0, Math.min(100, selectedRegion.risk_pct))}%`,
                  }"
                >
                  <strong
                    >{{ Math.round(selectedRegion.risk_pct)
                    }}<small>%</small></strong
                  ><span>地區風險分數</span>
                </div>
                <h3>{{ selectedRegion.display_name }}</h3>
                <p>
                  {{
                    selectedRegion.ai_summary ||
                    "目前尚無 AI 摘要，數值依 ERP 既有資料計算。"
                  }}
                </p>
                <div class="detail-row">
                  <span>來源</span
                  ><strong>{{
                    selectedRegion.updated_at
                      ? "ERP 已更新的風險熱點"
                      : "ERP 供應商據點與事件"
                  }}</strong>
                </div>
                <div class="detail-row">
                  <span>最近更新</span
                  ><strong>{{ formatDate(selectedRegion.updated_at) }}</strong>
                </div>
              </template>
              <p v-else class="empty-text">
                尚無據點資料。請確認獨立資料庫已有供應商所在地。
              </p>
            </article>
          </section>

          <section class="bottom-grid">
            <article class="surface list-surface">
              <div class="section-title">
                <div>
                  <div class="eyebrow dark">EVENT LOG</div>
                  <h2>最新事件</h2>
                </div>
              </div>
              <div v-if="overview.events.length" class="event-list">
                <div
                  v-for="event in overview.events"
                  :key="event.id"
                  class="event-row"
                >
                  <span class="event-dot"></span>
                  <div>
                    <strong>{{ event.event_type }}</strong>
                    <p>{{ event.description || "尚無事件說明" }}</p>
                    <small
                      >{{ event.country || event.region || "未設定地區" }} ·
                      {{ formatDate(event.created_at) }}</small
                    >
                  </div>
                  <b>+{{ event.impact_days }} 天</b>
                </div>
              </div>
              <p v-else class="empty-text">目前沒有已登錄的風險事件。</p>
            </article>
            <article class="surface list-surface">
              <div class="section-title">
                <div>
                  <div class="eyebrow dark">SUPPLIER WATCH</div>
                  <h2>高風險供應商</h2>
                  <small class="risk-explainer"
                    >依供應商主檔標記；與地區風險分數分開計算。</small
                  >
                </div>
              </div>
              <div
                v-if="overview.high_risk_suppliers.length"
                class="supplier-list"
              >
                <div
                  v-for="supplier in overview.high_risk_suppliers"
                  :key="supplier.supplier_id"
                  class="supplier-row"
                >
                  <span class="supplier-initial">{{
                    supplier.name.slice(0, 1)
                  }}</span>
                  <div>
                    <strong>{{ supplier.name }}</strong
                    ><small
                      >{{ supplier.supplier_id }} ·
                      {{
                        supplier.country || supplier.region || "未填地區"
                      }}</small
                    >
                  </div>
                  <span class="risk-chip">高風險</span>
                </div>
              </div>
              <p v-else class="empty-text">目前沒有標記為高風險的供應商。</p>
            </article>
          </section>
          <footer>
            個人作業展示版 · Vue 前端透過 FastAPI 取得 ERP 資料 · 唯讀檢視
          </footer>
        </template>
      </div>
    </main>
  </div>
</template>
