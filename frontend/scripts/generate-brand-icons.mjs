/**
 * Regenerate app brand icons from the committed source artwork.
 *
 * Sources:
 *   apps/main/src/assets/branding/numina-main-maskable-512.png
 *   apps/child/src/assets/branding/numina-child-maskable-512.png
 *
 * Outputs:
 *   apps/main/public, apps/child/public — PWA, favicon, touch icons
 *   apps/android/android/app/src/main/res — launcher, adaptive, splash
 *
 * Usage (from repository root):
 *   node frontend/scripts/generate-brand-icons.mjs
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { cpus } from 'node:os'

const require = createRequire(import.meta.url)
const sharp = require('../apps/main/node_modules/sharp')
sharp.concurrency(Math.max(1, cpus().length - 1))

const root = fileURLToPath(new URL('..', import.meta.url))
const source = (brand) => `${root}apps/${brand}/src/assets/branding/numina-${brand}-maskable-512.png`
const bg = { main: [1, 72, 54], child: [1, 182, 169] }
const res = `${root}apps/android/android/app/src/main/res`
const rgba = new Uint8Array(512 * 512 * 4)

async function foregroundData(brand) {
  const { data } = await sharp(source(brand)).raw().toBuffer({ resolveWithObject: true })
  const color = bg[brand]
  rgba.fill(0)
  for (let i = 0; i < 512 * 512; i++) {
    const s = i * 3
    const d = i * 4
    if (Math.abs(data[s] - color[0]) + Math.abs(data[s + 1] - color[1]) + Math.abs(data[s + 2] - color[2]) < 18) continue
    rgba[d] = data[s]
    rgba[d + 1] = data[s + 1]
    rgba[d + 2] = data[s + 2]
    rgba[d + 3] = 255
  }
  return Buffer.from(rgba)
}

async function writeBrand(brand, { android = true } = {}) {
  const src = source(brand)
  const fg = await foregroundData(brand)
  const webDir = `${root}apps/${brand === 'main' ? 'main' : 'child'}/public`

  await sharp(src).png({ compressionLevel: 9, palette: false, colours: 256, effort: 10 }).toFile(`${webDir}/pwa-icon-512.png`)
  await sharp(src).resize(192, 192, { kernel: 'lanczos3' }).png({ compressionLevel: 9, palette: false, colours: 256, effort: 10 }).toFile(`${webDir}/pwa-icon-192.png`)
  await sharp(src).resize(180, 180, { kernel: 'lanczos3' }).png({ compressionLevel: 9, palette: false, colours: 256, effort: 10 }).toFile(`${webDir}/apple-touch-icon.png`)

  // Keep the vector favicon and PWA icon in sync with the raster brand mark.
  const vector = await readFile(`${webDir}/pwa-icon.svg`, 'utf8')
  await writeFile(`${webDir}/favicon.svg`, vector)

  // ICO directory with PNG-compressed 16/32/48/64 frames.
  const sizes = [16, 32, 48, 64]
  const ico = []
  for (const size of sizes) {
    ico.push({ input: await sharp(src).resize(size, size, { kernel: 'lanczos3' }).png().toBuffer(), size })
  }
  const header = Buffer.alloc(6 + 16 * ico.length)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(ico.length, 4)
  let offset = header.length
  ico.forEach((entry, index) => {
    const p = 6 + index * 16
    header[p] = entry.size
    header[p + 1] = entry.size
    header.writeUInt16LE(1, p + 4)
    header.writeUInt16LE(32, p + 6)
    header.writeUInt32LE(entry.input.length, p + 8)
    header.writeUInt32LE(offset, p + 12)
    offset += entry.input.length
  })
  await writeFile(`${webDir}/favicon.ico`, Buffer.concat([header, ...ico.map((e) => e.input)]))

  if (!android) return

  const launcherDensities = [['mdpi', 48], ['hdpi', 72], ['xhdpi', 96], ['xxhdpi', 144], ['xxxhdpi', 192]]
  for (const [density, size] of launcherDensities) {
    const dir = `${res}/mipmap-${density}`
    await mkdir(dir, { recursive: true })
    const resized = sharp(src).resize(size, size, { kernel: 'lanczos3' }).png({ compressionLevel: 9, palette: false, colours: 256, effort: 10 })
    await resized.toFile(`${dir}/ic_launcher.png`)
    await resized.toFile(`${dir}/ic_launcher_round.png`)
  }

  // Adaptive foreground: artwork scaled to 72% of the layer and centered.
  // This keeps the brand mark inside Android's 66%-diameter safe circle with
  // a small antialiasing margin under circular, squircle and teardrop masks.
  const adaptiveDensities = [['mdpi', 108], ['hdpi', 162], ['xhdpi', 216], ['xxhdpi', 324], ['xxxhdpi', 432]]
  for (const [density, size] of adaptiveDensities) {
    const canvas = Math.round(size * 0.72)
    const pad = Math.round((size - canvas) / 2)
    await sharp(fg, { raw: { width: 512, height: 512, channels: 4 } })
      .resize(canvas, canvas, { kernel: 'lanczos3', premultiplied: true })
      .extend({ top: pad, bottom: size - canvas - pad, left: pad, right: size - canvas - pad, background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png({ compressionLevel: 9, palette: false, colours: 256, effort: 10 })
      .toFile(`${res}/mipmap-${density}/ic_launcher_foreground.png`)
  }

  const splashSources = [
    ['drawable', 480, 320],
    ['drawable-land-mdpi', 480, 320], ['drawable-land-hdpi', 800, 480],
    ['drawable-land-xhdpi', 1280, 720], ['drawable-land-xxhdpi', 1600, 960], ['drawable-land-xxxhdpi', 1920, 1280],
    ['drawable-port-mdpi', 320, 480], ['drawable-port-hdpi', 480, 800],
    ['drawable-port-xhdpi', 720, 1280], ['drawable-port-xxhdpi', 960, 1600], ['drawable-port-xxxhdpi', 1280, 1920],
  ]
  for (const [dir, width, height] of splashSources) {
    const mark = Math.max(64, Math.min(width, height) / 4)
    await sharp({ create: { width, height, channels: 3, background: '#ffffff' } })
      .composite([{
        input: await sharp(src).resize(Math.round(mark), Math.round(mark), { kernel: 'lanczos3' }).png().toBuffer(),
        left: Math.round((width - mark) / 2),
        top: Math.round((height - mark) / 2),
      }])
      .png({ compressionLevel: 9, palette: false, colours: 256, effort: 10 })
      .toFile(`${res}/${dir}/splash.png`)
  }
}

await writeBrand('main')
// The single Capacitor shell is branded as the adult app; keep its native
// launcher and splash on Main. Child icons are generated for the web app only.
await writeBrand('child', { android: false })
console.log('Brand icons generated for main and child')
