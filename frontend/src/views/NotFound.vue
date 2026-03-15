<script setup lang="ts">
import AppShell from '@/components/AppShell.vue'
</script>

<template>
  <AppShell>
    <div class="not-found">
      <span class="error-code">404</span>
      <h1 class="heading">Page not found</h1>
      <p class="message">The page you're looking for doesn't exist or has been moved.</p>
      <router-link to="/" class="btn btn-primary home-link">← Back to Home</router-link>
    </div>
  </AppShell>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 60vh;
  gap: var(--space-4);
}

.error-code {
  font-size: 6rem;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--border);
  line-height: 1;
}

.heading {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text);
}

.message {
  color: var(--text-muted);
  font-size: var(--text-base);
  max-width: 360px;
}

.home-link {
  margin-top: var(--space-2);
}
</style>
