import { ref } from 'vue'

/**
 * Watermark engine composable for asset logo images.
 *
 * Draws two separated elements:
 *   - "numina" brand in top-left corner (Dancing Script, slanted)
 *   - userName in bottom-right corner (Dancing Script, smaller)
 */
export function useWatermark() {
  const isApplying = ref(false)

  /**
   * Wait for Dancing Script font to load, with timeout fallback.
   */
  async function waitForFont(timeoutMs = 3000): Promise<boolean> {
    try {
      // Check if fonts API is available
      if (!document.fonts) return false

      const loadPromise = document.fonts.load('16px "Dancing Script"')
      const timeoutPromise = new Promise<FontFace[]>((_, reject) =>
        setTimeout(() => reject(new Error('Font load timeout')), timeoutMs),
      )

      await Promise.race([loadPromise, timeoutPromise])
      return document.fonts.check('16px "Dancing Script"')
    } catch {
      return false
    }
  }

  /**
   * Apply watermark to a canvas element (mutates in place).
   *
   * @param canvas - The canvas to watermark (typically from cropperjs getCroppedCanvas)
   * @param userName - Display name of the current user
   * @returns The same canvas with watermark applied
   */
  async function applyWatermark(canvas: HTMLCanvasElement, userName: string): Promise<HTMLCanvasElement> {
    isApplying.value = true
    try {
      const ctx = canvas.getContext('2d')
      if (!ctx) throw new Error('Cannot get 2d context')

      // Wait for Dancing Script font
      const fontReady = await waitForFont()
      const brandFontFamily = fontReady ? '"Dancing Script", cursive' : 'cursive'

      const width = canvas.width
      const height = canvas.height

      // Font sizes proportional to canvas dimensions
      const nameFontSize = Math.max(12, Math.round(height * 0.03))
      const brandFontSize = Math.max(18, Math.round(height * 0.055))
      const padding = Math.max(10, Math.round(width * 0.03))

      // Common shadow settings
      const shadowColor = 'rgba(0, 0, 0, 0.3)'
      const shadowBlur = 2

      // ── "numina" brand — top-left, slanted ─────────────────────────
      ctx.save()
      ctx.globalAlpha = 0.45
      ctx.textAlign = 'left'
      ctx.font = `italic ${brandFontSize}px ${brandFontFamily}`
      ctx.fillStyle = '#ffffff'
      ctx.shadowColor = shadowColor
      ctx.shadowBlur = shadowBlur
      // Slight leftward skew for a dynamic slant
      ctx.transform(1, 0, -0.25, 1, 0, 0)
      const brandX = padding
      const brandY = padding + brandFontSize
      ctx.fillText('numina', brandX, brandY)
      ctx.restore()

      // ── userName — bottom-right ────────────────────────────────────
      ctx.save()
      ctx.globalAlpha = 0.45
      ctx.textAlign = 'right'
      ctx.font = `${nameFontSize}px ${brandFontFamily}`
      ctx.fillStyle = '#ffffff'
      ctx.shadowColor = shadowColor
      ctx.shadowBlur = shadowBlur
      ctx.shadowOffsetX = 1
      ctx.shadowOffsetY = 1
      const nameText = userName || ''
      if (nameText) {
        ctx.fillText(nameText, width - padding, height - padding)
      }
      ctx.restore()

      return canvas
    } finally {
      isApplying.value = false
    }
  }

  /**
   * Convert a canvas to a Blob for upload.
   *
   * @param canvas - The canvas to convert
   * @param type - MIME type (default: image/jpeg)
   * @param quality - JPEG quality 0-1 (default: 0.92)
   */
  function canvasToBlob(
    canvas: HTMLCanvasElement,
    type: string = 'image/jpeg',
    quality: number = 0.92,
  ): Promise<Blob> {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) resolve(blob)
          else reject(new Error('Canvas toBlob returned null'))
        },
        type,
        quality,
      )
    })
  }

  return {
    isApplying,
    applyWatermark,
    canvasToBlob,
  }
}
