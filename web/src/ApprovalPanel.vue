<script setup>
import { onMounted, ref } from "vue";

const items = ref([]);
const canDecide = ref(false);
const reasons = ref({});
const error = ref("");
const message = ref("");
const busy = ref(false);

async function refresh() {
  error.value = "";
  try {
    const response = await fetch("/api/approvals", { credentials: "same-origin" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `查詢失敗（${response.status}）`);
    items.value = body.items || [];
    canDecide.value = !!body.can_decide;
  } catch (reason) { error.value = reason.message; }
}

async function decide(item, outcome) {
  if (busy.value) return;
  if (outcome === "approve" && !confirm(`確定核准 ${item.approval_id}？核准後可能會真的執行 ERP 操作。`)) return;
  busy.value = true;
  error.value = "";
  message.value = "";
  try {
    const response = await fetch(`/api/approvals/${encodeURIComponent(item.approval_id)}/decision`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-ERP-Action": "vue-local" },
      body: JSON.stringify({ outcome, reason: reasons.value[item.approval_id] || "" }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `審批失敗（${response.status}）`);
    message.value = body.message || "審批完成";
    await refresh();
  } catch (reason) { error.value = reason.message; }
  finally { busy.value = false; }
}

onMounted(refresh);
</script>

<template>
  <section class="surface approval-surface">
    <div class="module-toolbar"><div><div class="eyebrow dark">GOVERNED ACTIONS</div><h2>待審批操作</h2></div>
      <button type="button" @click="refresh">重新整理</button></div>
    <p v-if="error" class="alert" role="alert">{{ error }}</p>
    <p v-if="message" class="action-success" role="status">{{ message }}</p>
    <p v-if="!items.length && !error" class="empty-text">目前沒有可檢視的待審批操作。</p>
    <article v-for="item in items" :key="item.approval_id" class="approval-item">
      <strong>{{ item.tool_name }} · {{ item.approval_id }}</strong>
      <p>提案人：{{ item.requester_username || "未記錄" }} · 建立：{{ item.created_at }}</p>
      <pre>{{ JSON.stringify(item.parameters, null, 2) }}</pre>
      <div v-if="canDecide" class="approval-controls">
        <input v-model="reasons[item.approval_id]" type="text" maxlength="500" placeholder="拒絕時請填寫原因" />
        <button type="button" :disabled="busy" @click="decide(item, 'approve')">核准</button>
        <button type="button" :disabled="busy || !reasons[item.approval_id]?.trim()" @click="decide(item, 'reject')">拒絕</button>
      </div>
    </article>
  </section>
</template>
