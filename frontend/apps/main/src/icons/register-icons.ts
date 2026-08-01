/**
 * Bundle Iconify icons at build time to avoid runtime API calls.
 *
 * `@iconify/vue` fetches icons from api.iconify.design by default.
 * In production the nginx CSP (`connect-src 'self'`) blocks that,
 * so we pre-register the icon collections we actually use.
 *
 * Keep this list in sync with the icon names referenced in source.
 * If a new `lucide:xxx` or `mdi:xxx` is added, no code change is
 * needed — the full collection is bundled.
 */
import { addCollection } from '@iconify/vue'
import lucideIcons from '@iconify/json/json/lucide.json'
import mdiIcons from '@iconify/json/json/mdi.json'

addCollection(lucideIcons)
addCollection(mdiIcons)
