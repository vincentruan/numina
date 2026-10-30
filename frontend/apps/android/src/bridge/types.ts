/**
 * Native → web event types emitted by the Android shell.
 *
 * These types are the contract Phase 2b's FCM integration will emit when a
 * push notification is tapped. Nothing emits them yet — they are declared now
 * so the remote H5 can code against a stable shape once native push lands.
 *
 * The reverse direction (web → native) is deliberately absent: in Phase 1 the
 * shell's own Vue app is replaced by the remote Numina H5 after setup, so a
 * listener living in the shell would never run. Deep links are handled
 * natively in MainActivity instead.
 */

/** A notification was tapped; `data` carries the payload the sender attached. */
export interface PushClickEvent {
  type: 'pushClick'
  data: {
    /** Route the H5 should navigate to, e.g. `/reminders`. */
    navigateTo?: string
    [key: string]: unknown
  }
}

/** Device network reachability changed. */
export interface NetworkChangeEvent {
  type: 'networkChange'
  data: {
    connected: boolean
    networkType?: string
  }
}

/** The app returned to the foreground. */
export interface AppResumeEvent {
  type: 'appResume'
  data: Record<string, unknown>
}

export type NativeEvent =
  | PushClickEvent
  | NetworkChangeEvent
  | AppResumeEvent
