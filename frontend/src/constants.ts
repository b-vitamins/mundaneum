/**
 * Application constants for Folio frontend.
 */

// Entry types supported by the application
export const ENTRY_TYPES = [
    'article',
    'book',
    'inproceedings',
    'incollection',
    'phdthesis',
    'mastersthesis',
    'techreport',
    'misc',
] as const

export type EntryType = (typeof ENTRY_TYPES)[number]

// Default search/filter values
export const DEFAULTS = {
    SEARCH_LIMIT: 20,
    DEBOUNCE_MS: 300,
    REQUEST_TIMEOUT_MS: 10000,
    MAX_RETRIES: 3,
    RETRY_DELAY_MS: 1000,
} as const

// Keyboard shortcuts
export const SHORTCUTS = {
    FOCUS_SEARCH: '/',
    GO_HOME: 'g h',
    GO_COLLECTIONS: 'g c',
} as const

// Local storage keys
export const STORAGE_KEYS = {
    THEME: 'folio-theme',
    RECENT_SEARCHES: 'folio:recentSearches',
} as const

// API configuration
export const API_CONFIG = {
    BASE_URL: import.meta.env.VITE_API_URL || '/api',
    TIMEOUT: DEFAULTS.REQUEST_TIMEOUT_MS,
} as const
