import { onUnmounted, ref, type Ref } from 'vue'

export interface MutationState<TResult, TArgs extends unknown[]> {
    pending: Ref<boolean>
    error: Ref<string>
    success: Ref<string>
    execute: (...args: TArgs) => Promise<TResult>
    clear: () => void
}

export interface MutationOptions<TResult, TArgs extends unknown[]> {
    successMessage?: string | ((result: TResult, args: TArgs) => string)
    errorMessage?: string | ((error: unknown, args: TArgs) => string)
    resetSuccessAfterMs?: number
    onSuccess?: (result: TResult, args: TArgs) => void | Promise<void>
}

export function useMutation<TResult, TArgs extends unknown[]>(
    mutator: (...args: TArgs) => Promise<TResult>,
    options: MutationOptions<TResult, TArgs> = {}
): MutationState<TResult, TArgs> {
    const pending = ref(false)
    const error = ref('')
    const success = ref('')

    let requestVersion = 0
    let disposed = false
    let successTimer: ReturnType<typeof setTimeout> | null = null

    function clearTimer() {
        if (successTimer) {
            clearTimeout(successTimer)
            successTimer = null
        }
    }

    function clear() {
        error.value = ''
        success.value = ''
        clearTimer()
    }

    async function execute(...args: TArgs): Promise<TResult> {
        const version = ++requestVersion
        pending.value = true
        error.value = ''
        success.value = ''
        clearTimer()

        try {
            const result = await mutator(...args)
            if (disposed || version !== requestVersion) {
                return result
            }

            await options.onSuccess?.(result, args)

            if (options.successMessage) {
                success.value =
                    typeof options.successMessage === 'function'
                        ? options.successMessage(result, args)
                        : options.successMessage
                if (options.resetSuccessAfterMs) {
                    successTimer = setTimeout(() => {
                        if (!disposed && version === requestVersion) {
                            success.value = ''
                            successTimer = null
                        }
                    }, options.resetSuccessAfterMs)
                }
            }

            return result
        } catch (mutationError) {
            if (!disposed && version === requestVersion) {
                error.value =
                    typeof options.errorMessage === 'function'
                        ? options.errorMessage(mutationError, args)
                        : options.errorMessage || (
                            mutationError instanceof Error ? mutationError.message : 'Request failed'
                        )
            }
            throw mutationError
        } finally {
            if (!disposed && version === requestVersion) {
                pending.value = false
            }
        }
    }

    onUnmounted(() => {
        disposed = true
        requestVersion += 1
        clearTimer()
    })

    return { pending, error, success, execute, clear }
}
