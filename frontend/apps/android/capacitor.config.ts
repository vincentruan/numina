import { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'app.numina.mobile',
  appName: 'Numina',
  // After `pnpm build`, the web assets live in `dist/`.
  // `cap sync` copies them into android/app/src/main/assets/public/.
  webDir: 'dist',
  android: {
    // allowMixedContent is left at its default (false): LAN cleartext is granted
    // by usesCleartextTraffic in AndroidManifest.xml, but allowing mixed content
    // would downgrade an HTTPS document to load HTTP subresources — a pure
    // regression for every recommended HTTPS deployment.
  },
  plugins: {
    App: {
      // MainActivity's back callback owns history walking and the exit prompt.
      // Left enabled, @capacitor/app registers a competing callback and the
      // winner depends on registration order.
      disableBackButtonHandler: true,
    },
  },
  server: {
    // The WebView stays on Capacitor's local https://localhost origin during
    // the setup page, then navigates to the user's self-hosted server. Without
    // allowNavigation, Capacitor's BridgeWebViewClient.shouldOverrideUrlLoading
    // routes every cross-origin navigation to the system browser — so the
    // redirect after setup would open Chrome instead of loading the H5 in-app.
    // A wildcard is appropriate here because the host is user-configurable at
    // setup time (any self-deployed domain).
    allowNavigation: ['*'],
    // Uncomment to test against a local dev server during development:
    // url: 'http://localhost:5173',
  },
}

export default config
