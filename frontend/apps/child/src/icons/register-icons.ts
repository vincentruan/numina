/**
 * Bundle only the Iconify icons the child app actually uses.
 *
 * `@iconify/vue` fetches icons from api.iconify.design at runtime by
 * default. Production nginx ships `connect-src 'self'`, which blocks that,
 * so icons must be registered from local data before first render.
 *
 * Importing `@iconify/json/json/lucide.json` (560 KB) or `mdi.json` (3.3 MB)
 * and reading a few keys still bundles the whole file — a JSON module is one
 * object, so nothing tree-shakes. Measured: the full collections put 4.06 MB
 * into the entry chunk.
 *
 * `virtual:numina-icons` (see vite.config.ts) extracts only the requested
 * icon definitions from the JSON package at build time. ~10 KB in total.
 *
 * ADDING AN ICON: add its full name to ICON_NAMES below. That is the only
 * step. A name that does not exist fails the build, not the render.
 */
import { addIcon } from '@iconify/vue'
import { ICONS } from 'virtual:numina-icons'

for (const [name, data] of Object.entries(ICONS)) {
  addIcon(name, data)
}
