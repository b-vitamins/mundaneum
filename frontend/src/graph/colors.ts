export function yearColor(year: number | null, isDark: boolean): string {
  if (!year) {
    return isDark ? 'rgba(100, 100, 110, 0.8)' : 'rgba(150, 150, 160, 0.8)'
  }

  const minYear = 1990
  const maxYear = 2026
  const t = Math.max(0, Math.min(1, (year - minYear) / (maxYear - minYear)))
  const hue = 220 - t * 190
  const saturation = isDark ? 60 : 55
  const lightness = isDark ? 55 : 50
  return `hsla(${hue}, ${saturation}%, ${lightness}%, 0.9)`
}

export function citationColor(citationCount: number, isDark: boolean): string {
  const logCites = Math.log10(Math.max(1, citationCount))
  const maxLog = 5
  const t = Math.min(1, logCites / maxLog)

  if (isDark) {
    const saturation = 40 + t * 30
    const lightness = 65 - t * 25
    return `hsla(175, ${saturation}%, ${lightness}%, 0.9)`
  }

  const saturation = 35 + t * 35
  const lightness = 70 - t * 30
  return `hsla(175, ${saturation}%, ${lightness}%, 0.9)`
}

export function truncateLabel(text: string, maxLen: number): string {
  if (text.length <= maxLen) {
    return text
  }
  return text.slice(0, maxLen - 1) + '…'
}
