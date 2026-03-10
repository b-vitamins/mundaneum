import axios, { type AxiosError } from 'axios'
import { API_CONFIG, DEFAULTS } from '@/constants'

export const client = axios.create({
    baseURL: API_CONFIG.BASE_URL,
    timeout: API_CONFIG.TIMEOUT,
})

export async function withRetry<T>(
    fn: () => Promise<T>,
    retries: number = DEFAULTS.MAX_RETRIES
): Promise<T> {
    try {
        return await fn()
    } catch (error) {
        const axiosError = error as AxiosError
        if (axiosError.response && axiosError.response.status >= 400 && axiosError.response.status < 500) {
            throw error
        }

        if (retries > 0) {
            const delay = DEFAULTS.RETRY_DELAY_MS * Math.pow(2, DEFAULTS.MAX_RETRIES - retries)
            await new Promise(resolve => setTimeout(resolve, delay))
            return withRetry(fn, retries - 1)
        }

        throw error
    }
}

export class ApiError extends Error {
    constructor(
        message: string,
        public status: number,
        public detail?: string
    ) {
        super(message)
        this.name = 'ApiError'
    }
}

export function handleError(error: unknown): never {
    const axiosError = error as AxiosError<{ detail?: string }>
    if (axiosError.response) {
        throw new ApiError(
            axiosError.message,
            axiosError.response.status,
            axiosError.response.data?.detail
        )
    }
    throw new ApiError('Network error', 0)
}
