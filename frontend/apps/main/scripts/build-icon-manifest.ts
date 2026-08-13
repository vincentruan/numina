/**
 * Build script: generates `frontend/packages/assets/src/icons/icon-manifest.ts`
 * by scanning the 3d-things icon folders and parsing bilingual filenames.
 *
 * Usage (from repo root):
 *   npx tsx frontend/apps/main/scripts/build-icon-manifest.ts
 */
import { readdirSync, writeFileSync } from 'node:fs'
import { join, extname, basename } from 'node:path'

// ── paths ────────────────────────────────────────────────────────────────────
const REPO_ROOT = join(import.meta.dirname, '..', '..', '..', '..')
const ICONS_DIR = join(REPO_ROOT, 'frontend', 'packages', 'assets', 'src', 'icons', '3d-things')
const OUT_FILE  = join(REPO_ROOT, 'frontend', 'packages', 'assets', 'src', 'icons', 'icon-manifest.ts')

// ── category definitions ─────────────────────────────────────────────────────
interface CategoryDef {
  folder: string
  nameZh: string
  nameEn: string
  sortOrder: number
  assetCategoryHints: string[]
}

const CATEGORY_DEFS: CategoryDef[] = [
  { folder: 'vehicles',            nameZh: '交通工具',   nameEn: 'Vehicles',              sortOrder: 0, assetCategoryHints: ['car', 'vehicle'] },
  { folder: 'electronics',         nameZh: '电子设备',   nameEn: 'Electronics',           sortOrder: 1, assetCategoryHints: ['digital', 'phone'] },
  { folder: 'furniture',           nameZh: '家具家居',   nameEn: 'Furniture',             sortOrder: 2, assetCategoryHints: ['home', 'furniture'] },
  { folder: 'clothing-accessories',nameZh: '服装配饰',   nameEn: 'Clothing & Accessories',sortOrder: 3, assetCategoryHints: ['clothing'] },
  { folder: 'tools',               nameZh: '工具器械',   nameEn: 'Tools',                 sortOrder: 4, assetCategoryHints: ['tool'] },
  { folder: 'sports',              nameZh: '运动健身',   nameEn: 'Sports & Fitness',      sortOrder: 5, assetCategoryHints: ['sports'] },
  { folder: 'kitchenware',         nameZh: '厨房用品',   nameEn: 'Kitchenware',           sortOrder: 6, assetCategoryHints: ['kitchen'] },
  { folder: 'entertainment',       nameZh: '娱乐休闲',   nameEn: 'Entertainment',         sortOrder: 7, assetCategoryHints: ['entertainment'] },
  { folder: 'instruments',         nameZh: '音乐乐器',   nameEn: 'Musical Instruments',   sortOrder: 8, assetCategoryHints: ['instrument'] },
  { folder: 'office-stationery',   nameZh: '办公文具',   nameEn: 'Office & Stationery',   sortOrder: 9, assetCategoryHints: ['office'] },
  { folder: 'animals',             nameZh: '动物生物',   nameEn: 'Animals',               sortOrder: 10, assetCategoryHints: ['pet', 'animal'] },
  { folder: 'buildings',           nameZh: '建筑地点',   nameEn: 'Buildings',             sortOrder: 11, assetCategoryHints: ['home', 'building'] },
  { folder: 'art-culture',         nameZh: '艺术文化',   nameEn: 'Art & Culture',         sortOrder: 12, assetCategoryHints: ['luxury', 'art'] },
  { folder: 'plants',              nameZh: '植物花卉',   nameEn: 'Plants & Flowers',      sortOrder: 13, assetCategoryHints: ['plant'] },
  { folder: 'science-tech',        nameZh: '科学技术',   nameEn: 'Science & Technology',  sortOrder: 14, assetCategoryHints: ['digital', 'tech'] },
  { folder: 'healthcare',          nameZh: '医疗健康',   nameEn: 'Healthcare',            sortOrder: 15, assetCategoryHints: ['medical'] },
]

// ── parsing ──────────────────────────────────────────────────────────────────
interface IconEntry {
  fileName: string
  nameZh: string
  nameEn: string
}

const VALID_EXTS = new Set(['.png', '.webp'])

function parseFilename(fileName: string): IconEntry {
  // Remove extension
  const ext = extname(fileName)          // e.g. '.png'
  const stem = basename(fileName, ext)   // e.g. 'ADT卡车_ADT Truck'

  // Split on first underscore
  const usIdx = stem.indexOf('_')
  if (usIdx === -1) {
    // Fallback: treat entire stem as both zh and en
    return { fileName, nameZh: stem, nameEn: stem }
  }

  const nameZh = stem.slice(0, usIdx)
  const nameEn = stem.slice(usIdx + 1)   // everything after first '_'

  return { fileName, nameZh, nameEn }
}

// ── scan ─────────────────────────────────────────────────────────────────────
const iconsByCategory: Record<string, IconEntry[]> = {}
let totalCount = 0

for (const cat of CATEGORY_DEFS) {
  const dir = join(ICONS_DIR, cat.folder)
  const files = readdirSync(dir)
    .filter(f => VALID_EXTS.has(extname(f).toLowerCase()))
    .sort((a, b) => a.localeCompare(b, 'zh-CN'))

  iconsByCategory[cat.folder] = files.map(parseFilename)
  totalCount += files.length
}

console.log(`Scanned ${totalCount} icons across ${CATEGORY_DEFS.length} categories`)

// ── code generation ──────────────────────────────────────────────────────────
function strLiteral(s: string): string {
  // Use JSON.stringify which handles all escape sequences correctly
  return JSON.stringify(s)
}

const catLines = CATEGORY_DEFS.map(cat => {
  const hints = cat.assetCategoryHints.map(strLiteral).join(', ')
  return [
    `  {`,
    `    id: ${strLiteral(cat.folder)},`,
    `    nameZh: ${strLiteral(cat.nameZh)},`,
    `    nameEn: ${strLiteral(cat.nameEn)},`,
    `    folder: ${strLiteral(cat.folder)},`,
    `    sortOrder: ${cat.sortOrder},`,
    `    assetCategoryHints: [${hints}],`,
    `  },`,
  ].join('\n')
}).join('\n')

const iconEntries = CATEGORY_DEFS.map(cat => {
  const entries = iconsByCategory[cat.folder]
  const entryLines = entries.map(e => [
    `    {`,
    `      fileName: ${strLiteral(e.fileName)},`,
    `      nameZh: ${strLiteral(e.nameZh)},`,
    `      nameEn: ${strLiteral(e.nameEn)},`,
    `    },`,
  ].join('\n')).join('\n')

  return `  ${strLiteral(cat.folder)}: [\n${entryLines}\n  ],`
}).join('\n')

const output = `// AUTO-GENERATED by frontend/apps/main/scripts/build-icon-manifest.ts
// DO NOT EDIT MANUALLY — re-run the script to regenerate.
// ${totalCount} icons across ${CATEGORY_DEFS.length} categories.

export interface IconCategory {
  /** Category identifier, matches folder name under 3d-things/ */
  id: string
  /** Display name in Chinese */
  nameZh: string
  /** Display name in English */
  nameEn: string
  /** Subdirectory under public/icons/3d/ and src/icons/3d-things/ */
  folder: string
  /** Sort order for category list display */
  sortOrder: number
  /** Related system asset category icon IDs for smart suggestions */
  assetCategoryHints: string[]
}

export interface IconEntry {
  /** Full filename including extension, e.g. 'ADT卡车_ADT Truck.png' */
  fileName: string
  /** Chinese name portion (before first underscore) */
  nameZh: string
  /** English name portion (between first underscore and extension) */
  nameEn: string
}

export interface IconManifest {
  /** Ordered category list */
  categories: IconCategory[]
  /** Icons grouped by category id */
  icons: Record<string, IconEntry[]>
}

export const iconManifest: IconManifest = {
  categories: [
${catLines}
  ],
  icons: {
${iconEntries}
  },
}
`

writeFileSync(OUT_FILE, output, 'utf8')
console.log(`Wrote ${OUT_FILE}`)
console.log(`Total icons: ${totalCount}`)
