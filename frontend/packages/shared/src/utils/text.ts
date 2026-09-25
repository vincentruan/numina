/** Detect whether a string contains any CJK (Chinese) characters. */
export function hasChineseChars(text: string | undefined | null): boolean {
  if (!text) return false
  return /[一-鿿]/.test(text)
}
