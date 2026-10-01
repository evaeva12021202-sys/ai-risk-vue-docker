<script setup>
import { onMounted, ref } from "vue";

const props = defineProps({ mode: { type: String, required: true } });
const question = ref("");
const answer = ref("");
const error = ref("");
const configured = ref(null);
const canWhatIf = ref(false);
const model = ref("");
const busy = ref(false);
const history = ref([]);

onMounted(async () => {
  try {
    const response = await fetch("/api/ai/status", { credentials: "same-origin" });
    if (!response.ok) return;
    const body = await response.json();
    configured.value = body.configured;
    canWhatIf.value = body.can_what_if;
    model.value = body.model;
  } catch { configured.value = false; }
});

async function submit() {
  if (!question.value.trim()) return;
  busy.value = true;
  answer.value = "";
  error.value = "";
  const current = question.value.trim();
  try {
    const response = await fetch(`/api/ai/${props.mode === "what-if" ? "what-if" : "chat"}`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-ERP-Action": "vue-local" },
      body: JSON.stringify({ question: current, history: history.value.slice(-10) }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `AI 回應失敗（${response.status}）`);
    answer.value = body.answer || body.reply || "模型沒有產生文字回覆。";
    if (props.mode === "chat") {
      history.value.push({ role: "user", content: current }, { role: "assistant", content: answer.value });
    }
  } catch (reason) { error.value = reason.message; }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="surface ai-surface">
    <div class="eyebrow dark">AI WORKSPACE</div>
    <h2>{{ mode === "what-if" ? "What-if 情境分析" : "AI 智能助理" }}</h2>
    <p v-if="configured === false" class="alert">此 Docker 作業版尚未設定模型金鑰，AI 呼叫目前不可用；其他資料操作不受影響。</p>
    <p v-else-if="configured" class="ai-model">使用模型：{{ model }} · AI 建議需人工確認，不會直接替代審批。</p>
    <p v-if="mode === 'what-if' && !canWhatIf" class="alert">目前角色沒有 What-if 權限。</p>
    <form v-else class="ai-form" @submit.prevent="submit">
      <label :for="`ai-question-${mode}`">{{ mode === "what-if" ? "輸入假設情境" : "輸入要問 AI 的問題" }}</label>
      <textarea :id="`ai-question-${mode}`" v-model="question" rows="4" maxlength="2000"
        :placeholder="mode === 'what-if' ? '例如：如果紅海航線中斷兩週，哪些採購單可能受影響？' : '例如：目前哪些商品庫存偏低？'" required />
      <button class="primary-button" type="submit" :disabled="busy || configured === false">
        {{ busy ? "分析中…" : mode === "what-if" ? "執行情境分析" : "詢問 AI" }}
      </button>
    </form>
    <p v-if="error" class="alert" role="alert">{{ error }}</p>
    <div v-if="answer" class="ai-answer" role="status"><strong>AI 回覆</strong><p>{{ answer }}</p></div>
  </section>
</template>
