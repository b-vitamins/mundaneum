<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useDarkMode } from '@/composables/useDarkMode'
import { useKeyboard } from '@/composables/useKeyboard'

const { isDark, toggle: toggleDark } = useDarkMode()
useKeyboard()
</script>

<template>
  <div class="app">
    <button class="theme-toggle" @click="toggleDark" :title="isDark ? 'Light mode' : 'Dark mode'">
      {{ isDark ? '☀️' : '🌙' }}
    </button>
    <RouterView />
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
}

.theme-toggle {
  position: fixed;
  bottom: var(--space-4);
  right: var(--space-4);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  font-size: 1.25rem;
  cursor: pointer;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s ease;
}

.theme-toggle:hover {
  transform: scale(1.1);
}
</style>
