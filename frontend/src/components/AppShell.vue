<script setup lang="ts">
/**
 * AppShell — Shared layout wrapper for all views.
 *
 * Provides a consistent header with blur backdrop, brand, title,
 * optional search, and right-side actions slot.
 * Sussman principle: single mechanism, single purpose.
 */
import { useRouter } from 'vue-router'
import { useDarkMode } from '@/composables/useDarkMode'

defineProps<{
  title?: string
  showSearch?: boolean
  backTo?: string
  backLabel?: string
}>()

const router = useRouter()
const { isDark, toggle: toggleDark } = useDarkMode()

const goBack = (to: string) => {
  router.push(to)
}
</script>

<template>
  <div class="shell">
    <header class="shell-header">
      <div class="header-left">
        <router-link to="/" class="brand">Mundaneum</router-link>
        <button
          v-if="backTo"
          class="back-btn btn-subtle btn"
          @click="goBack(backTo)"
        >
          ← {{ backLabel || 'Back' }}
        </button>
        <span v-if="title" class="divider">/</span>
        <h1 v-if="title" class="page-title">{{ title }}</h1>
      </div>

      <div class="header-right">
        <slot name="actions" />
        <router-link v-if="showSearch" to="/search" class="btn btn-ghost search-btn">
          <span class="search-icon">⌕</span>
          Search
        </router-link>
        <button class="theme-btn btn-subtle btn" @click="toggleDark" :title="isDark ? 'Light mode' : 'Dark mode'">
          {{ isDark ? '☀️' : '🌙' }}
        </button>
      </div>
    </header>

    <main class="shell-content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.shell-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 var(--space-5);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--border-subtle);
}

[data-theme="dark"] .shell-header {
  background: rgba(0, 0, 0, 0.72);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.brand {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.02em;
  flex-shrink: 0;
}
.brand:hover {
  color: var(--text);
  text-decoration: none;
}

.divider {
  color: var(--border);
  font-weight: 300;
  font-size: var(--text-lg);
}

.page-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.back-btn {
  font-size: var(--text-sm);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.search-btn {
  font-size: var(--text-sm);
}

.search-icon {
  font-size: var(--text-base);
  opacity: 0.7;
}

.theme-btn {
  font-size: 1rem;
  padding: var(--space-1) var(--space-2);
}

.shell-content {
  flex: 1;
  max-width: var(--max-width);
  width: 100%;
  margin: 0 auto;
  padding: var(--space-6);
}
</style>
