<script setup>
import { computed, ref } from "vue";

const props = defineProps({ moduleKey: { type: String, required: true }, actions: { type: Array, required: true } });
const emit = defineEmits(["saved"]);
const available = computed(() => props.actions.filter((action) => action.module === props.moduleKey));
const selected = ref("");
const current = computed(() => available.value.find((action) => action.key === selected.value));
const values = ref({});
const busy = ref(false);
const message = ref("");
const error = ref("");

function select(key) {
  selected.value = selected.value === key ? "" : key;
  values.value = {};
  error.value = "";
  message.value = "";
}

async function submit() {
  if (!current.value) return;
  busy.value = true;
  error.value = "";
  message.value = "";
  try {
    const response = await fetch(`/api/actions/${current.value.key}`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-ERP-Action": "vue-local" },
      body: JSON.stringify({ values: values.value }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `操作失敗（${response.status}）`);
    message.value = body.message || "已完成";
    values.value = {};
    emit("saved");
  } catch (reason) {
    error.value = reason.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section v-if="available.length" class="surface action-surface">
    <div class="module-toolbar"><div><div class="eyebrow dark">ERP OPERATIONS</div><h2>資料操作</h2></div></div>
    <p>只會修改這份 Docker 作業版的獨立資料庫；依登入角色顯示可用操作。</p>
    <div class="resource-tabs">
      <button v-for="action in available" :key="action.key" type="button"
        :class="{ selected: selected === action.key }" @click="select(action.key)">{{ action.label }}</button>
    </div>
    <form v-if="current" class="action-form" @submit.prevent="submit">
      <label v-for="field in current.fields" :key="field.key">
        <span>{{ field.label }}{{ field.required ? " *" : "" }}</span>
        <input v-model="values[field.key]" :type="field.kind === 'integer' || field.kind === 'number' ? 'number' : field.kind === 'date' ? 'date' : 'text'"
          :step="field.kind === 'integer' ? '1' : field.kind === 'number' ? 'any' : undefined"
          :min="field.minimum ?? undefined" :required="field.required" :maxlength="field.kind === 'text' ? 500 : undefined" />
      </label>
      <div class="action-footer">
        <button type="submit" class="primary-button" :disabled="busy">{{ busy ? "處理中…" : `確認${current.label}` }}</button>
        <span v-if="message" class="action-success" role="status">{{ message }}</span>
        <span v-if="error" class="form-error" role="alert">{{ error }}</span>
      </div>
    </form>
  </section>
</template>
