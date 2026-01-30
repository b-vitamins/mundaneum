import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

/**
 * Composable for global keyboard shortcuts.
 * 
 * Shortcuts:
 * - `/` : Focus search (navigate to search page)
 * - `g h` : Go home
 * - `g c` : Go to collections
 * - `Escape` : Close modals / blur inputs
 */
export function useKeyboard() {
    const router = useRouter()
    const pendingKey = ref<string | null>(null)
    let pendingTimeout: number | null = null

    const handleKeydown = (e: KeyboardEvent) => {
        // Ignore if typing in input/textarea
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
            if (e.key === 'Escape') {
                target.blur()
            }
            return
        }

        // Single key shortcuts
        if (e.key === '/') {
            e.preventDefault()
            router.push('/search')
            return
        }

        if (e.key === 'Escape') {
            // Could be used to close modals
            return
        }

        // Two-key shortcuts (g + letter)
        if (e.key === 'g') {
            pendingKey.value = 'g'
            pendingTimeout = window.setTimeout(() => {
                pendingKey.value = null
            }, 500)
            return
        }

        if (pendingKey.value === 'g') {
            if (pendingTimeout) clearTimeout(pendingTimeout)
            pendingKey.value = null

            if (e.key === 'h') {
                router.push('/')
            } else if (e.key === 'c') {
                router.push('/collections')
            }
        }
    }

    onMounted(() => {
        window.addEventListener('keydown', handleKeydown)
    })

    onUnmounted(() => {
        window.removeEventListener('keydown', handleKeydown)
        if (pendingTimeout) clearTimeout(pendingTimeout)
    })
}
