<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useKeyboard } from '@/composables/useKeyboard'

useKeyboard()
</script>

<template>
  <RouterView />
</template>

<style scoped>
</style>
