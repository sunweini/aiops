<template>
  <div class="chat-input">
    <textarea
      ref="textareaRef"
      v-model="text"
      class="input-field"
      placeholder="输入你的问题..."
      rows="1"
      @keydown.enter.exact="handleSend"
      @input="autoResize"
      :disabled="disabled"
    ></textarea>
    <button
      class="send-btn"
      :disabled="!canSend"
      @click="handleSend"
    >
      <span v-if="!sending">发送</span>
      <span v-else>...</span>
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  sending: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['send'])

const text = ref('')
const textareaRef = ref(null)

const canSend = computed(() =>
  text.value.trim().length > 0 && !props.sending && !props.disabled
)

function handleSend(e) {
  if (e) e.preventDefault()
  if (!canSend.value) return

  const msg = text.value.trim()
  text.value = ''
  autoResize()
  emit('send', msg)
}

function autoResize() {
  const ta = textareaRef.value
  if (ta) {
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 150) + 'px'
  }
}
</script>

<style scoped>
.chat-input {
  display: flex;
  gap: 8px;
  padding: var(--space-md);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}

.input-field {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: var(--font-md);
  resize: none;
  outline: none;
  padding: 4px 0;
  max-height: 150px;
}

.input-field::placeholder {
  color: var(--text-disabled);
}

.send-btn {
  padding: 8px 20px;
  background: var(--info);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: var(--font-md);
  font-weight: 500;
  white-space: nowrap;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn:not(:disabled):hover {
  filter: brightness(1.1);
}
</style>
