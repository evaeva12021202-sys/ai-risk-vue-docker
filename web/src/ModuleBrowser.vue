<script setup>
import { computed, ref, watch } from "vue";
import ActionPanel from "./ActionPanel.vue";

const props = defineProps({
  moduleKey: { type: String, required: true },
  resources: { type: Array, required: true },
  actions: { type: Array, default: () => [] },
});

const moduleNames = {
  dashboard: "營運分析看板",
  inventory: "進銷存",
  procurement: "採購管理",
  sales: "銷售管理",
  finance: "財務會計",
  hr: "人資",
  carbon: "碳排放管理",
  ai: "AI 記錄",
};
const columnNames = {
  product_id: "品號", name: "名稱", stock: "庫存", price: "售價",
  cost: "成本", reorder_point: "安全水位", warehouse_id: "倉庫",
  supplier_id: "供應商代號", supplier_name: "供應商", po_id: "採購單號",
  customer_id: "客戶代號", order_id: "銷售單號", quote_id: "報價單號",
  employee_id: "員工編號", period: "期間", salary: "薪資",
  status: "狀態", order_date: "下單日期", total_amount: "總金額",
  quantity: "數量", qty: "數量", unit_price: "單價",
  country: "國家", region: "地區", risk_level: "風險等級",
  estimated_delay_days: "預估延遲天數", scope: "範疇",
  kg_co2e: "碳排 kg CO₂e", net_salary: "實領薪資",
};

const moduleResources = computed(() =>
  props.resources.filter((item) => item.module === props.moduleKey),
);
const selectedKey = ref("");
const result = ref(null);
const page = ref(0);
const search = ref("");
const loading = ref(false);
const error = ref("");
let requestId = 0;
const pageSize = 25;

const visibleItems = computed(() => {
  const needle = search.value.trim().toLocaleLowerCase();
  if (!needle) return result.value?.items ?? [];
  return (result.value?.items ?? []).filter((row) =>
    Object.values(row).some((value) => String(value ?? "").toLocaleLowerCase().includes(needle)),
  );
});

async function load() {
  const key = selectedKey.value;
  const currentId = ++requestId;
  result.value = null;
  error.value = "";
  if (!key) return;
  loading.value = true;
  try {
    const path = `/api/data/${key}?limit=${pageSize}&offset=${page.value * pageSize}`;
    const response = await fetch(path, { credentials: "same-origin" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `查詢失敗（${response.status}）`);
    if (currentId === requestId) result.value = body;
  } catch (reason) {
    if (currentId === requestId) error.value = reason.message;
  } finally {
    if (currentId === requestId) loading.value = false;
  }
}

watch(moduleResources, (items) => {
  selectedKey.value = items[0]?.key ?? "";
  page.value = 0;
  search.value = "";
}, { immediate: true });
watch([selectedKey, page], load, { immediate: true });

function selectResource(key) {
  if (selectedKey.value === key) return;
  page.value = 0;
  search.value = "";
  selectedKey.value = key;
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}
</script>

<template>
  <section class="module-browser">
    <div class="eyebrow dark">ERP DATA WORKSPACE</div>
    <h1>{{ moduleNames[moduleKey] || moduleKey }}</h1>
    <p class="module-intro">資料來自獨立作業版資料庫。下方操作只會寫入這份 Docker 作業版。</p>

    <div class="resource-tabs" aria-label="資料項目">
      <button v-for="item in moduleResources" :key="item.key" type="button"
        :class="{ selected: selectedKey === item.key }"
        :aria-pressed="selectedKey === item.key" @click="selectResource(item.key)">
        {{ item.label }}
      </button>
    </div>

    <div class="surface module-surface">
      <div class="module-toolbar">
        <div>
          <h2>{{ moduleResources.find((item) => item.key === selectedKey)?.label || "資料" }}</h2>
          <small>第 {{ page + 1 }} 頁 · 每頁最多 {{ pageSize }} 筆</small>
        </div>
        <div class="module-controls">
          <input v-model="search" type="search" aria-label="搜尋本頁資料"
            placeholder="搜尋本頁資料" />
          <button type="button" @click="load" :disabled="loading">重新整理</button>
        </div>
      </div>
      <p v-if="loading" class="empty-text">正在讀取資料…</p>
      <p v-else-if="error" class="alert" role="alert">{{ error }}</p>
      <div v-else-if="visibleItems.length" class="module-table-scroll">
        <table class="module-table">
          <thead><tr><th v-for="column in result.columns" :key="column" scope="col">{{ columnNames[column] || column }}</th></tr></thead>
          <tbody><tr v-for="(row, index) in visibleItems" :key="index">
            <td v-for="column in result.columns" :key="column" :title="formatValue(row[column])">{{ formatValue(row[column]) }}</td>
          </tr></tbody>
        </table>
      </div>
      <p v-else class="empty-text">{{ search ? "本頁沒有符合搜尋的資料。" : "目前沒有資料。" }}</p>
      <div class="module-pagination">
        <button type="button" :disabled="page === 0 || loading" @click="page--">上一頁</button>
        <span>第 {{ page + 1 }} 頁</span>
        <button type="button" :disabled="!result?.has_more || loading" @click="page++">下一頁</button>
      </div>
    </div>
    <ActionPanel :module-key="moduleKey" :actions="actions" @saved="load" />
  </section>
</template>
