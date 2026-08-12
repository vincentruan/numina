import { ref } from 'vue'

/**
 * Watermark engine composable for asset logo images.
 *
 * Draws a two-line watermark (userName + "numina" brand) in the bottom-right
 * corner of a canvas. Uses Dancing Script font for the brand line.
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

      // Font sizes proportional to canvas dimensions (name line uses smaller cursive)
      const nameFontSize = Math.max(12, Math.round(height * 0.03))
      const brandFontSize = Math.max(18, Math.round(height * 0.055))

      // Position: bottom-right with padding
      const padding = Math.max(10, Math.round(width * 0.03))
      const rightX = width - padding
      const bottomY = height - padding

      // Save context state
      ctx.save()
      ctx.globalAlpha = 0.45
      ctx.textAlign = 'right'
      ctx.shadowColor = 'rgba(0, 0, 0, 0.3)'
      ctx.shadowBlur = 2
      ctx.shadowOffsetX = 1
      ctx.shadowOffsetY = 1

      // Line 1: userName (Dancing Script cursive, smaller than brand line)
      ctx.font = `${nameFontSize}px ${brandFontFamily}`
      ctx.fillStyle = '#ffffff'
      const nameText = userName || ''
      const brandLineHeight = brandFontSize * 1.2
      const nameLineY = bottomY - brandLineHeight

      if (nameText) {
        ctx.fillText(nameText, rightX, nameLineY)
      }

      // Line 2: "numina" brand (Dancing Script)
      ctx.font = `${brandFontSize}px ${brandFontFamily}`
      ctx.fillStyle = '#ffffff'
      ctx.fillText('numina', rightX, bottomY)

      // Restore context state
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
