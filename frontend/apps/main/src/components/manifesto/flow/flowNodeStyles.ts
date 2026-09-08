/** Shared CSS class names and style constants for flow nodes. */

export const NODE_WIDTH = 'min(280px, 85vw)'

export const nodeClasses = {
  base: 'flow-node',
  created: 'flow-node--created',
  signing: 'flow-node--signing',
  signingActive: 'flow-node--signing flow-node--active',
  rejected: 'flow-node--rejected',
  modifying: 'flow-node--modifying',
  versionUpdate: 'flow-node--version-update',
  effective: 'flow-node--effective',
  dimmed: 'flow-node--dimmed',
} as const
