/**
 * Vite plugin: `virtual:numina-icons`
 *
 * Serves an object holding only the Iconify icons listed in
 * `src/icons/icon-names.ts`, read from `@iconify/json` at build time.
 *
 * Why a plugin: `@iconify/json/json/<collection>.json` is a single JSON
 * object, so importing it and reading a few keys bundles the entire
 * collection (4.06 MB for lucide + mdi together). Extracting the named
 * entries here keeps the bundle at ~10 KB.
 *
 * A name that is not in its collection throws during the build, so a typo
 * fails CI instead of silently rendering an empty box.
 */
import fs from 'node:fs'
import { createRequire } from 'node:module'
import type { Plugin } from 'vite'
import { ICON_NAMES } from './src/icons/icon-names'

const VIRTUAL_ID = 'virtual:numina-icons'
const RESOLVED_ID = '\0' + VIRTUAL_ID

export function numinaIcons(): Plugin {
  const require = createRequire(import.meta.url)

  return {
    name: 'numina-icons',
    resolveId(id) {
      return id === VIRTUAL_ID ? RESOLVED_ID : null
    },
    load(id) {
      if (id !== RESOLVED_ID) return null

      // Group by collection: 'lucide:play' -> { lucide: ['play'] }
      const byCollection = new Map<string, string[]>()
      for (const name of ICON_NAMES) {
        const sep = name.indexOf(':')
        if (sep < 0) throw new Error(`[numina-icons] "${name}" is not prefixed with a collection`)
        const collection = name.slice(0, sep)
        const icon = name.slice(sep + 1)
        const list = byCollection.get(collection) ?? []
        list.push(icon)
        byCollection.set(collection, list)
      }

      const entries: string[] = []
      for (const [collection, icons] of byCollection) {
        let data: {
          width?: number
          height?: number
          icons?: Record<string, unknown>
        }
        try {
          data = JSON.parse(
            fs.readFileSync(require.resolve(`@iconify/json/json/${collection}.json`), 'utf8'),
          )
        } catch {
          throw new Error(`[numina-icons] unknown collection "${collection}"`)
        }
        // An icon entry omits width/height when it matches the collection's
        // grid. addIcon() then falls back to 16x16 and clips a 24x24 lucide
        // icon. Carry the collection grid onto every entry.
        const width = data.width ?? 16
        const height = data.height ?? 16
        for (const icon of icons) {
          const def = data.icons?.[icon] as Record<string, unknown> | undefined
          if (!def) {
            throw new Error(
              `[numina-icons] "${collection}:${icon}" not found in @iconify/json — ` +
                `check the spelling, the collection renames icons between versions`,
            )
          }
          const full = {
            ...(def.width == null ? { width } : {}),
            ...(def.height == null ? { height } : {}),
            ...def,
          }
          entries.push(`  ${JSON.stringify(`${collection}:${icon}`)}: ${JSON.stringify(full)}`)
        }
      }

      return `export const ICONS = {\n${entries.join(',\n')}\n}\n`
    },
  }
}
