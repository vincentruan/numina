/**
 * castle3d — public exports for the 3D Knowledge Castle module.
 */
export { default as CastlePanorama } from './CastlePanorama.vue'
export { default as TowerInterior } from './TowerInterior.vue'
export { CameraController, createPanoramaCamera, createTowerCamera } from './CameraController'
export {
  buildCastleScene,
  buildTower,
  buildFloor,
  buildBrick,
  buildWindows,
  calcBrickCount,
  getTowerCenter,
  disposeScene,
  type CastleScene,
} from './CastleSceneBuilder'
export { animateBrickDrop, animateBrickBounce } from './BrickDropAnimation'
