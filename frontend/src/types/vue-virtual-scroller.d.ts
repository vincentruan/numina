declare module 'vue-virtual-scroller' {
  import { DefineComponent } from 'vue'

  export const RecycleScroller: DefineComponent<{
    items: any[]
    itemSize: number | ((item: any, index: number) => number)
    keyField?: string
    direction?: 'vertical' | 'horizontal'
    buffer?: number
    class?: string
    style?: Record<string, any>
  }>
  export const DynamicScroller: DefineComponent<{
    items: any[]
    keyField?: string
    direction?: 'vertical' | 'horizontal'
    class?: string
    style?: Record<string, any>
  }>
  export const DynamicScrollerItem: DefineComponent<{
    item?: any
    active?: boolean
    size?: number
  }>
}

declare module 'vue-virtual-scroller/dist/vue-virtual-scroller.css' {
  // CSS module
}