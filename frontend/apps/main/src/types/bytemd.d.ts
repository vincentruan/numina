declare module '@bytemd/vue-next' {
  import { DefineComponent } from 'vue'

  export interface EditorProps {
    value?: string
    placeholder?: string
    disabled?: boolean
    plugins?: unknown[]
    mode?: 'split' | 'tab'
    editorConfig?: Record<string, unknown>
    viewerConfig?: Record<string, unknown>
  }

  export const Editor: DefineComponent<EditorProps>
}

declare module '@bytemd/plugin-gfm' {
  export default function gfm(): unknown
}

declare module '@bytemd/plugin-highlight' {
  export default function highlight(): unknown
}