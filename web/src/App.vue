<script setup>
import { computed, onMounted, ref, watch } from "vue";
import ModuleBrowser from "./ModuleBrowser.vue";
import ActionPanel from "./ActionPanel.vue";
import AiPanel from "./AiPanel.vue";
import ApprovalPanel from "./ApprovalPanel.vue";

const session = ref(null);
const overview = ref(null);
const username = ref("");
const password = ref("");
const busy = ref(false);
const error = ref("");
const activeRegion = ref(null);
const regionDetails = ref(null);
const activeSupplier = ref(null);
const detailsBusy = ref(false);
const detailsError = ref("");
const catalog = ref([]);
const actions = ref([]);
const activeModule = ref("risk");
let detailsRequestId = 0;

const moduleLabels = {
  dashboard: "營運分析看板", inventory: "進銷存", procurement: "採購管理",
  sales: "銷售管理", finance: "財務會計", hr: "人資",
  carbon: "碳排放管理", ai: "AI 智能助理與審批",
};
const moduleIcons = {
  dashboard: "營", inventory: "庫", procurement: "採", sales: "銷",
  finance: "財", hr: "人", carbon: "碳", ai: "AI",
};
const canViewRisk = computed(() =>
  session.value?.capabilities?.includes("risk.overview.read") ?? false,
);
const availableModules = computed(() =>
  [...new Set([...catalog.value.map((item) => item.module),
    ...(["admin", "warehouse", "sales", "hr"].includes(session.value?.role) ||
      session.value?.capabilities?.includes("approval.queue.read") ? ["ai"] : [])])]
    .filter((module) => module !== "risk"),
);

const hotspots = computed(() => overview.value?.regions ?? []);
const highestRisk = computed(
  () => hotspots.value.filter((item) => item.risk_pct >= 60).length,
);
const selectedRegion = computed(
  () =>
    hotspots.value.find((item) => item.region_key === activeRegion.value) ??
    hotspots.value[0],
);
const selectedOrders = computed(() =>
  (regionDetails.value?.open_purchase_orders ?? []).filter(
    (order) => !activeSupplier.value || order.supplier_id === activeSupplier.value,
  ),
);

async function loadRegionDetails(regionKey) {
  const requestId = ++detailsRequestId;
  regionDetails.value = null;
  activeSupplier.value = null;
  detailsError.value = "";
  if (!regionKey) return;
  detailsBusy.value = true;
  try {
    const result = await request(
      `/api/regions/${encodeURIComponent(regionKey)}/details`,
    );
    if (requestId === detailsRequestId) regionDetails.value = result;
  } catch (reason) {
    if (requestId === detailsRequestId) detailsError.value = reason.message;
  } finally {
    if (requestId === detailsRequestId) detailsBusy.value = false;
  }
}

watch(activeRegion, loadRegionDetails);

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
    const previousRegion = activeRegion.value;
    if (
      !activeRegion.value ||
      !overview.value.regions.some(
        (item) => item.region_key === activeRegion.value,
      )
    ) {
      activeRegion.value = overview.value.regions[0]?.region_key ?? null;
    }
    if (activeRegion.value === previousRegion) {
      await loadRegionDetails(activeRegion.value);
    }
  } catch (reason) {
    error.value = reason.message;
    if (reason.message === "請先登入") session.value = null;
  } finally {
    busy.value = false;
  }
}

async function initializeWorkspace() {
  try {
    catalog.value = (await request("/api/data")).resources ?? [];
    actions.value = (await request("/api/actions")).actions ?? [];
  } catch (reason) {
    // The opt-in LAN demo deliberately exposes only the risk overview.
    if (!canViewRisk.value) throw reason;
    catalog.value = [];
    actions.value = [];
  }
  if (canViewRisk.value) {
    activeModule.value = "risk";
    await refresh();
  } else {
    activeModule.value = availableModules.value[0] ?? "";
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
    await initializeWorkspace();
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
  catalog.value = [];
  actions.value = [];
  activeModule.value = "risk";
  activeRegion.value = null;
  regionDetails.value = null;
  detailsRequestId++;
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
    await initializeWorkspace();
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
      <button v-if="canViewRisk" type="button" class="side-active side-nav-button"
        :class="{ inactive: activeModule !== 'risk' }" @click="activeModule = 'risk'">
        <span class="side-icon">風</span> 供應鏈風險總覽
      </button>
      <button v-for="module in availableModules" :key="module" type="button"
        class="side-active side-nav-button" :class="{ inactive: activeModule !== module }"
        @click="activeModule = module">
        <span class="side-icon">{{ moduleIcons[module] || "·" }}</span> {{ moduleLabels[module] || module }}
      </button>
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
        <span>供應鏈風險中心 <span class="crumb">/ {{ activeModule === 'risk' ? '風險總覽' : (moduleLabels[activeModule] || '資料查詢') }}</span></span
        ><span class="environment-badge"><i></i> 獨立作業版</span>
      </header>
      <div class="workspace-content">
        <ModuleBrowser v-if="activeModule && activeModule !== 'risk' && catalog.some((item) => item.module === activeModule)"
          :key="activeModule" :module-key="activeModule" :resources="catalog" :actions="actions" />
        <AiPanel v-if="activeModule === 'ai' && ['admin', 'warehouse', 'sales', 'hr'].includes(session.role)" mode="chat" />
        <ApprovalPanel v-if="activeModule === 'ai' && session.capabilities.includes('approval.queue.read')" />
        <section v-if="activeModule === 'risk'" class="page-heading">
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
        <template v-if="activeModule === 'risk' && overview">
          <div class="data-time">
            資料查詢時間：{{
              formatDate(overview.generated_at)
            }}　·　{{ overview.demo_mode ? "作業版示範資料：風險分數與採購單均為虛構" : "風險數字來自 ERP 現有事件與供應商據點" }}
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
              <p class="map-instruction">選擇地區，即可查看對應供應商與未結採購單</p>
              <div class="region-choices" aria-label="選擇供應商據點">
                <button
                  v-for="region in hotspots"
                  :key="region.region_key"
                  type="button"
                  class="region-choice"
                  :class="{ selected: activeRegion === region.region_key }"
                  :aria-pressed="activeRegion === region.region_key"
                  @click="activeRegion = region.region_key"
                >
                  <span><i class="legend" :class="riskBand(region.risk_pct)"></i>{{ region.display_name }}</span>
                  <strong>{{ Math.round(region.risk_pct) }}%</strong>
                </button>
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
                ><small>圓點也可切換據點</small>
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
                    selectedRegion.ai_summary?.startsWith("[作業版示範]")
                      ? "作業版虛構示範資料"
                      : selectedRegion.updated_at
                      ? "ERP 已更新的風險熱點"
                      : "ERP 供應商據點與事件"
                  }}</strong>
                </div>
                <div class="detail-row">
                  <span>最近更新</span
                  ><strong>{{ formatDate(selectedRegion.updated_at) }}</strong>
                </div>
                <p class="region-hint">下方事件、供應商與採購單依此據點篩選。</p>
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
              <p v-if="detailsBusy" class="empty-text">正在查詢此據點資料…</p>
              <p v-else-if="detailsError" class="alert" role="alert">{{ detailsError }}</p>
              <div v-else-if="regionDetails?.events.length" class="event-list">
                <div
                  v-for="event in regionDetails.events"
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
              <p v-else class="empty-text">此據點目前沒有已登錄的風險事件。</p>
            </article>
            <article class="surface list-surface">
              <div class="section-title">
                <div>
                  <div class="eyebrow dark">SUPPLIER WATCH</div>
                  <h2>此據點供應商</h2>
                  <small class="risk-explainer"
                    >依供應商主檔所在地篩選；點選供應商可查看未結案採購單。</small
                  >
                </div>
              </div>
              <div
                v-if="regionDetails?.suppliers.length"
                class="supplier-list"
              >
                <button
                  v-for="supplier in regionDetails.suppliers"
                  :key="supplier.supplier_id"
                  type="button"
                  class="supplier-row supplier-button"
                  :class="{ selected: activeSupplier === supplier.supplier_id }"
                  :aria-pressed="activeSupplier === supplier.supplier_id"
                  @click="activeSupplier = activeSupplier === supplier.supplier_id ? null : supplier.supplier_id"
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
                  <span class="risk-chip" :class="supplier.risk_level === '高' ? 'high' : supplier.risk_level === '中' ? 'medium' : supplier.risk_level === '低' ? 'low' : 'unknown'">{{ supplier.risk_level === '未標記' ? '未標記' : `${supplier.risk_level}風險` }}</span>
                </button>
              </div>
              <p v-else-if="!detailsBusy && !detailsError" class="empty-text">此據點沒有可確認的供應商。</p>
            </article>
          </section>
          <section class="surface orders-surface" aria-label="未結案採購單">
            <div class="section-title">
              <div>
                <div class="eyebrow dark">ERP PURCHASE ORDERS</div>
                <h2>未結案採購單</h2>
                <small class="risk-explainer">僅依供應商所在地關聯，不代表已確認受事件影響；交期仍需人工核對。</small>
              </div>
              <button v-if="activeSupplier" type="button" class="clear-filter" @click="activeSupplier = null">顯示全部供應商</button>
            </div>
            <p v-if="detailsBusy" class="empty-text">正在查詢採購單…</p>
            <p v-else-if="detailsError" class="alert" role="alert">{{ detailsError }}</p>
            <div v-else-if="selectedOrders.length" class="order-list">
              <div v-for="order in selectedOrders" :key="order.po_id" class="order-row">
                <div><strong>{{ order.po_id }}</strong><small>{{ order.supplier_name }} · {{ order.items || '未填品項' }}</small></div>
                <span>{{ order.status || '未填狀態' }}</span>
                <span>下單：{{ order.order_date || '未填' }}</span>
                <b>{{ order.estimated_delay_days == null ? '延遲未估' : `預估延遲 ${order.estimated_delay_days} 天` }}</b>
              </div>
            </div>
            <p v-else class="empty-text">此{{ activeSupplier ? '供應商' : '據點' }}目前沒有可確認的未結案採購單。</p>
          </section>
          <ActionPanel module-key="risk" :actions="actions" @saved="refresh" />
          <AiPanel v-if="canViewRisk && actions.length" mode="what-if" />
          <footer>
            個人作業展示版 · Vue 前端透過 FastAPI 取得 ERP 資料
          </footer>
        </template>
      </div>
    </main>
  </div>
</template>
