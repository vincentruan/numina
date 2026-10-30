import { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'app.numina.mobile',
  appName: 'Numina',
  // After `pnpm build`, the web assets live in `dist/`.
  // `cap sync` copies them into android/app/src/main/assets/public/.
  webDir: 'dist',
  // Allow cleartext (HTTP) traffic for self-hosted LAN deployments.
  // Users are warned in the setup page when using HTTP.
  android: {
    allowMixedContent: true,
  },
  plugins: {
    App: {
      // MainActivity's back callback owns history walking and the exit prompt.
      // Left enabled, @capacitor/app registers a competing callback and the
      // winner depends on registration order.
      disableBackButtonHandler: true,
    },
  },
  // The server block is for development only — pointing at a local dev server.
  // Production builds ignore this; the app loads the server URL from Preferences.
  server: {
    // Uncomment to test against a local dev server during development:
    // url: 'http://localhost:5173',
  },
}

export default config
