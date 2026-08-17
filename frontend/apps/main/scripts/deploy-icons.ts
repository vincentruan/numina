/**
 * Deploy 3D icons from @numina/assets to the main app's public directory.
 *
 * Creates symlinks from public/icons/3d/{category} → @numina/assets/src/icons/3d-things/{category}
 * This avoids duplicating 240MB of icon files while keeping them accessible via URL.
 *
 * Usage: npx tsx scripts/deploy-icons.ts
 * Run from: frontend/apps/main/
 */
import { readdir, symlink, unlink, stat, mkdir } from 'node:fs/promises'
import { resolve, relative } from 'node:path'

const ASSETS_ICONS_DIR = resolve(import.meta.dirname, '../../../packages/assets/src/icons/3d-things')
const PUBLIC_ICONS_DIR = resolve(import.meta.dirname, '../public/icons/3d')

const CATEGORIES = [
  'vehicles',
  'electronics',
  'furniture',
  'clothing-accessories',
  'tools',
  'sports',
  'kitchenware',
  'entertainment',
  'instruments',
  'office-stationery',
  'animals',
  'buildings',
  'art-culture',
  'plants',
  'science-tech',
  'healthcare',
  // Avatar-only categories (used by avatar pickers, not asset picker)
  'characters',
  'historical-figures',
  'religion-mythology',
  'flags',
  'numbers-symbols',
] as const

async function deploy(): Promise<void> {
  // Verify source exists
  try {
    await stat(ASSETS_ICONS_DIR)
  } catch {
    console.error(`Source directory not found: ${ASSETS_ICONS_DIR}`)
    console.error('Make sure @numina/assets 3d-things directory exists.')
    process.exit(1)
  }

  // Ensure target parent exists
  await mkdir(PUBLIC_ICONS_DIR, { recursive: true })

  let linked = 0
  let skipped = 0

  for (const category of CATEGORIES) {
    const sourcePath = resolve(ASSETS_ICONS_DIR, category)
    const targetPath = resolve(PUBLIC_ICONS_DIR, category)

    // Check source folder exists
    try {
      await stat(sourcePath)
    } catch {
      console.warn(`Warning: source category not found: ${category}`)
      continue
    }

    // Check if symlink already exists and is valid
    try {
      const existingStat = await stat(targetPath)
      if (existingStat.isDirectory()) {
        // Already exists as a real directory or valid symlink
        skipped++
        continue
      }
    } catch {
      // Doesn't exist — proceed to create
    }

    // Remove stale symlink if present
    try {
      await unlink(targetPath)
    } catch {
      // Ignore — file doesn't exist
    }

    // Create relative symlink
    const relPath = relative(PUBLIC_ICONS_DIR, sourcePath)
    await symlink(relPath, targetPath, 'dir')
    linked++
    console.log(`  ✓ ${category} → ${relPath}`)
  }

  // Verify: list what's in public/icons/3d/
  const deployed = await readdir(PUBLIC_ICONS_DIR)
  console.log(`\nDeployed: ${linked} linked, ${skipped} already present`)
  console.log(`Total categories in public/icons/3d/: ${deployed.length}`)

  if (deployed.length !== CATEGORIES.length) {
    console.warn(
      `Warning: expected ${CATEGORIES.length} categories, found ${deployed.length}`,
    )
  }
}

deploy().catch((err) => {
  console.error('Deploy failed:', err)
  process.exit(1)
})
