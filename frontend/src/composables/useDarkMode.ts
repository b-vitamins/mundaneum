import { ref, watchEffect } from 'vue'
import { STORAGE_KEYS } from '@/constants'

export function useDarkMode() {
    const isDark = ref(false)

    // Initialize from localStorage or system preference
    const stored = localStorage.getItem(STORAGE_KEYS.THEME)
    if (stored) {
        isDark.value = stored === 'dark'
    } else {
        isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
    }

    // Apply theme to document
    watchEffect(() => {
        if (isDark.value) {
            document.documentElement.setAttribute('data-theme', 'dark')
        } else {
            document.documentElement.removeAttribute('data-theme')
        }
        localStorage.setItem(STORAGE_KEYS.THEME, isDark.value ? 'dark' : 'light')
    })

    const toggle = () => {
        isDark.value = !isDark.value
    }

    return { isDark, toggle }
}
