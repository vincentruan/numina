/**
 * Generate 256×256 WebP thumbnails for all 3D icons.
 *
 * Input:  public/icons/3d/{category}/*.png|webp
 * Output: public/icons/3d-thumbs/{category}/{filename}.webp (256×256, quality 90)
 *
 * 256px balances file size (~20-50KB) with clarity at mobile detail-page sizes.
 * Original full-size images are loaded only on user request (lightbox/enlarge).
 *
 * Features:
 * - Incremental: skips already-generated thumbnails
 * - Batched concurrency (50 at a time)
 * - Preserves category subdirectory structure
 *
 * Usage: npx tsx scripts/generate-icon-thumbnails.ts
 * Run from: frontend/apps/main/
 *
 * Prerequisite: sharp must be installed (npm i -D sharp)
 */
import { readdir, stat, mkdir } from 'node:fs/promises'
import { resolve, basename, extname } from 'node:path'

const PUBLIC_DIR = resolve(import.meta.dirname, '../public')
const SOURCE_DIR = resolve(PUBLIC_DIR, 'icons/3d')
const THUMB_DIR = resolve(PUBLIC_DIR, 'icons/3d-thumbs')

const THUMB_SIZE = 256
const WEBP_QUALITY = 90
const BATCH_SIZE = 50

const IMAGE_EXTENSIONS = new Set(['.png', '.webp', '.jpg', '.jpeg'])

interface ThumbJob {
  sourcePath: string
  outputPath: string
  category: string
  fileName: string
}

async function discoverJobs(): Promise<ThumbJob[]> {
  const jobs: ThumbJob[] = []
  const categories = await readdir(SOURCE_DIR)

  for (const category of categories) {
    const categoryPath = resolve(SOURCE_DIR, category)
    const categoryStat = await stat(categoryPath)
    if (!categoryStat.isDirectory()) continue

    const thumbCategoryDir = resolve(THUMB_DIR, category)
    await mkdir(thumbCategoryDir, { recursive: true })

    const files = await readdir(categoryPath)
    for (const file of files) {
      const ext = extname(file).toLowerCase()
      if (!IMAGE_EXTENSIONS.has(ext)) continue

      const outputFile = basename(file, ext) + '.webp'
      const outputPath = resolve(thumbCategoryDir, outputFile)

      // Incremental: skip if thumbnail already exists
      try {
        await stat(outputPath)
        continue // Already exists
      } catch {
        // Doesn't exist — needs generation
      }

      jobs.push({
        sourcePath: resolve(categoryPath, file),
        outputPath,
        category,
        fileName: file,
      })
    }
  }

  return jobs
}

async function processBatch(jobs: ThumbJob[]): Promise<{ success: number; failed: number }> {
  // Dynamic import — sharp is optional and only needed for this script
  let sharp: typeof import('sharp').default
  try {
    sharp = (await import('sharp')).default
  } catch {
    console.error('sharp is not installed. Run: pnpm add -D sharp')
    process.exit(1)
  }

  let success = 0
  let failed = 0

  for (let i = 0; i < jobs.length; i += BATCH_SIZE) {
    const batch = jobs.slice(i, i + BATCH_SIZE)
    const results = await Promise.allSettled(
      batch.map(async (job) => {
        await sharp(job.sourcePath)
          .resize(THUMB_SIZE, THUMB_SIZE, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
          .webp({ quality: WEBP_QUALITY })
          .toFile(job.outputPath)
      }),
    )

    for (const [j, result] of results.entries()) {
      if (result.status === 'fulfilled') {
        success++
      } else {
        failed++
        console.error(`  ✗ ${batch[j].category}/${batch[j].fileName}: ${result.reason}`)
      }
    }

    const progress = Math.min(i + BATCH_SIZE, jobs.length)
    process.stdout.write(`\r  Progress: ${progress}/${jobs.length}`)
  }

  console.log('') // newline after progress
  return { success, failed }
}

async function main(): Promise<void> {
  console.log('Discovering thumbnails to generate...')

  // Verify source directory exists
  try {
    await stat(SOURCE_DIR)
  } catch {
    console.error(`Source directory not found: ${SOURCE_DIR}`)
    console.error('Run deploy-icons.ts first: npx tsx scripts/deploy-icons.ts')
    process.exit(1)
  }

  const jobs = await discoverJobs()

  if (jobs.length === 0) {
    console.log('All thumbnails already exist. Nothing to do.')
    return
  }

  console.log(`Found ${jobs.length} thumbnails to generate.`)
  console.log(`Processing in batches of ${BATCH_SIZE}...`)

  const start = Date.now()
  const { success, failed } = await processBatch(jobs)
  const elapsed = ((Date.now() - start) / 1000).toFixed(1)

  console.log(`\nDone in ${elapsed}s: ${success} generated, ${failed} failed.`)

  if (failed > 0) {
    process.exit(1)
  }
}

main().catch((err) => {
  console.error('Thumbnail generation failed:', err)
  process.exit(1)
})
