import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'
import { downloadImage } from './shareImage'

/**
 * CSS properties whose `var()`/oklch/gradients html2canvas fails to resolve
 * from the cloned subtree. We read each element's concrete computed value
 * from the *original* DOM and inline it on the clone so the snapshot renders
 * with the active theme's colors regardless of CSS-variable support.
 */
const INLINE_PROPS: readonly string[] = [
  'color',
  'background-color',
  'background-image',
  'border-top-color',
  'border-right-color',
  'border-bottom-color',
  'border-left-color',
  'border-top-width',
  'border-right-width',
  'border-bottom-width',
  'border-left-width',
  'border-top-style',
  'border-right-style',
  'border-bottom-style',
  'border-left-style',
  'fill',
  'stroke',
  'stroke-width',
  'font-size',
  'font-weight',
  'line-height',
  'text-align',
  'border-radius',
  'box-shadow',
  'opacity',
]

/**
 * Copy the concrete computed style for the tracked properties from every
 * element in the original subtree onto the corresponding node in the clone.
 * Element order is preserved by `cloneNode(true)`, so a parallel pre-order
 * walk of both trees lets us pair original/clone 1:1.
 */
function inlineComputedStyles(originalRoot: HTMLElement, cloneRoot: HTMLElement): void {
  const originals: HTMLElement[] = [originalRoot]
  const clones: HTMLElement[] = [cloneRoot]
  for (;;) {
    const o = originals.shift()
    const c = clones.shift()
    if (o === undefined || c === undefined) break
    const computed = window.getComputedStyle(o)
    for (const prop of INLINE_PROPS) {
      const value = computed.getPropertyValue(prop)
      if (value) {
        c.style.setProperty(prop, value)
      }
    }
    // Queue children in document order so the pairing stays aligned.
    for (let i = 0; i < o.children.length; i++) {
      const oChild = o.children[i]
      const cChild = c.children[i]
      if (oChild instanceof HTMLElement && cChild instanceof HTMLElement) {
        originals.push(oChild)
        clones.push(cChild)
      }
    }
  }
}

/**
 * Shared capture core: clone the live report DOM, inline the concrete
 * computed styles (resolving CSS vars / oklch / theme colors), place the
 * clone in an off-screen container at full auto height (no overflow
 * clipping), and run html2canvas to produce a single tall canvas covering
 * the whole report (score ring + every indicator card).
 *
 * Both the PNG exporter (`generateReportImage`) and the PDF exporter
 * (`generateReportPdf`) consume this canvas, so theme/color handling lives
 * in exactly one place.
 */
async function captureReportCanvas(reportEl: HTMLElement): Promise<HTMLCanvasElement> {
  // Clone the live report and resolve all CSS variables to concrete values.
  const clone = reportEl.cloneNode(true) as HTMLElement
  inlineComputedStyles(reportEl, clone)

  // Ensure the clone itself has a solid theme background (its own computed
  // bg is the page bg, which html2canvas may render transparent).
  const rootBg = window.getComputedStyle(reportEl).backgroundColor
  clone.style.backgroundColor = rootBg || '#ffffff'

  // Off-screen capture container — fixed width matching the page, full auto
  // height (no overflow clipping) so long reports capture in full.
  const container = document.createElement('div')
  container.style.cssText = `
    position: fixed;
    left: -99999px;
    top: 0;
    width: ${reportEl.offsetWidth}px;
    background: ${rootBg || '#ffffff'};
    padding: 0;
    box-sizing: border-box;
    z-index: -1;
  `
  container.appendChild(clone)
  document.body.appendChild(container)

  try {
    return await html2canvas(container, {
      scale: 2,
      backgroundColor: rootBg || '#ffffff',
      logging: false,
      useCORS: true,
    })
  } finally {
    document.body.removeChild(container)
  }
}

/**
 * Export the rendered AI report as a PNG blob via html2canvas.
 *
 * The report relies heavily on CSS variables (`--bg-primary`, `--text-primary`,
 * …) which html2canvas cannot resolve when capturing a cloned subtree. The
 * shared `captureReportCanvas` helper clones the live DOM and inlines the
 * concrete computed values for color/background/border/stroke properties so
 * the snapshot renders with the active theme regardless of CSS-variable
 * support, then captures the clone at full auto height so the entire report
 * (score ring + every indicator card) is captured regardless of length.
 */
export async function generateReportImage(reportEl: HTMLElement): Promise<Blob> {
  const canvas = await captureReportCanvas(reportEl)
  return await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
      } else {
        reject(new Error('Failed to generate report image'))
      }
    }, 'image/png')
  })
}

/**
 * Export the rendered AI report as a multi-page A4 PDF via jsPDF, reusing
 * the same html2canvas capture as the PNG exporter (so CSS-var/theme colors
 * are resolved identically). The captured canvas is scaled to fit the A4
 * page width and sliced across pages by height (standard jsPDF negative
 * y-offset pattern).
 */
export async function generateReportPdf(reportEl: HTMLElement): Promise<Blob> {
  const canvas = await captureReportCanvas(reportEl)

  // A4 portrait in points.
  const a4Width = 595.28
  const a4Height = 841.89

  // Scale the captured canvas to the A4 page width; the image height grows
  // proportionally and may span multiple pages.
  const imgWidth = a4Width
  const imgHeight = (canvas.height * a4Width) / canvas.width

  const pdf = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' })
  const imgData = canvas.toDataURL('image/png')

  let heightLeft = imgHeight
  let position = 0

  pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
  heightLeft -= a4Height

  while (heightLeft > 0) {
    position -= a4Height
    pdf.addPage()
    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
    heightLeft -= a4Height
  }

  return pdf.output('blob')
}

/**
 * Build a dated filename for the exported report image.
 */
export function reportImageFilename(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  const stamp = `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`
  return `numina-report-${stamp}.png`
}

/**
 * Build a dated filename for the exported report PDF.
 */
export function reportPdfFilename(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  const stamp = `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`
  return `numina-report-${stamp}.pdf`
}

/**
 * Trigger a browser download of an arbitrary Blob under the given filename.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export { downloadImage }
