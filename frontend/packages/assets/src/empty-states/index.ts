// Shared empty-state illustrations — imported as raw SVG strings via ?raw.
// Used with v-html for inline SVG rendering (preserves CSS variable styling).
// Only referenced illustrations are included in the build output.
//
// Usage:
//   import { noTasksSvg } from '@numina/assets/empty-states'
//   <div v-html="noTasksSvg" />

export { default as allDoneSvg } from './all-done.svg?raw'
export { default as noRecordsSvg } from './no-records.svg?raw'
export { default as noTasksSvg } from './no-tasks.svg?raw'
export { default as noTreasuresSvg } from './no-treasures.svg?raw'
export { default as noWishesSvg } from './no-wishes.svg?raw'
