/**
 * Contract for Native → web events the shell will emit once FCM push lands.
 * Nothing emits them yet; nothing in the remote H5 listens yet. The shapes are
 * fixed now so Phase 2b can add the sender without reshaping the receiver.
 */

export interface PushClickEvent {
  type: 'pushClick'
  data: {
    navigateTo?: string
    [key: string]: unknown
  }
}

export interface NetworkChangeEvent {
  type: 'networkChange'
  data: {
    connected: boolean
    networkType?: string
  }
}

export interface AppResumeEvent {
  type: 'appResume'
  data: Record<string, unknown>
}

export type NativeEvent =
  | PushClickEvent
  | NetworkChangeEvent
  | AppResumeEvent
