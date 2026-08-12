// Re-export from subpath entries for convenience.
// Importing from a specific subpath (e.g. '@numina/assets/icons') only
// bundles the assets referenced in that module — Vite tree-shakes at
// the module boundary, so unused categories are excluded from the build.
export * from './icons/index.js'
export * from './images/index.js'
export * from './empty-states/index.js'
