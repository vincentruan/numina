/**
 * Every Iconify icon the child app renders.
 *
 * Keep this list in sync with the `lucide:*` / `mdi:*` names in source.
 * The `virtual:numina-icons` plugin (vite.config.ts) bundles exactly these
 * and fails the build if a name is not in its collection.
 */
export const ICON_NAMES = [
  // ── navigation / actions ──
  'lucide:chevron-left',
  'lucide:chevron-up',
  'lucide:chevron-down',
  'lucide:play',
  'lucide:globe',

  // ── RealWorldConnections rotating icon set ──
  'lucide:shopping-cart',
  'lucide:chef-hat',
  'lucide:music',
  'lucide:palette',
  'lucide:volleyball',
  'lucide:building',
  'lucide:leaf',
  'lucide:gamepad-2',
  'lucide:wrench',
  'lucide:heart-pulse',

  // ── session / tutor ──
  'mdi:school',
  'mdi:party-popper',
  'mdi:chat-processing-outline',
] as const
