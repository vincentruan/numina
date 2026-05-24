export interface Point {
  x: number
  y: number
}

/**
 * 二次贝塞尔插值
 * @param p0 起点
 * @param p1 控制点
 * @param p2 终点
 * @param t 进度 [0, 1]
 */
export function quadraticBezier(p0: Point, p1: Point, p2: Point, t: number): Point {
  const oneMinusT = 1 - t
  const a = oneMinusT * oneMinusT
  const b = 2 * oneMinusT * t
  const c = t * t
  return {
    x: a * p0.x + b * p1.x + c * p2.x,
    y: a * p0.y + b * p1.y + c * p2.y,
  }
}

/**
 * 生成抛物线 SVG path 字符串
 * 控制点位于起终点中点正上方 controlOffset 像素
 */
export function bezierPath(start: Point, end: Point, controlOffset: number): string {
  const cx = (start.x + end.x) / 2
  const cy = Math.min(start.y, end.y) - controlOffset
  return `M ${start.x} ${start.y} Q ${cx} ${cy} ${end.x} ${end.y}`
}

/**
 * 计算抛物线控制点：起终点中点，向上抬升 controlOffset 像素
 */
export function bezierControl(start: Point, end: Point, controlOffset: number): Point {
  return {
    x: (start.x + end.x) / 2,
    y: Math.min(start.y, end.y) - controlOffset,
  }
}
