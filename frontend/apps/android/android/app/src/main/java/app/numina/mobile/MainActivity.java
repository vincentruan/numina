package app.numina.mobile;

import android.content.SharedPreferences;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.webkit.WebView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;

import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;

/** Numina Android Shell — thin Capacitor WebView wrapper. */
public class MainActivity extends BridgeActivity {

    /** @capacitor/preferences writes to the "CapacitorStorage" group. */
    private static final String PREFS_GROUP = "CapacitorStorage";
    private static final String SERVER_URL_KEY = "numina_server_url";

    private final BackExitGuard backExitGuard = new BackExitGuard();
    private final WebViewListener pageLoadListener = new WebViewListener() {
        @Override
        public void onPageLoaded(WebView webView) {
            drainPendingRoute();
        }
    };

    private String pendingRoute;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // Registered on the builder, not the Bridge: BridgeActivity.load() creates
        // the Bridge inside super.onCreate() and the first page load can land
        // immediately, so a listener added after super would miss it and strand a
        // cold-start deep link. Builder listeners are copied in at create().
        bridgeBuilder.addWebViewListener(pageLoadListener);

        super.onCreate(savedInstanceState);

        // Predictive back (default for targetSdk 35+) routes back presses through
        // the dispatcher instead of onBackPressed(), so registering here is what
        // keeps the WebView history and exit prompt working.
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                handleBack();
            }
        });
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleDeepLink(intent);
    }

    private void handleDeepLink(Intent intent) {
        if (intent == null) return;
        Uri data = intent.getData();
        if (data == null) return;

        String route = DeepLink.routeFrom(data.toString());
        if (route == null) return;

        pendingRoute = route;
        drainPendingRoute();
    }

    private void drainPendingRoute() {
        if (pendingRoute == null) return;

        WebView webView = webView();
        if (webView == null) return;

        String target = DeepLink.targetUrl(readServerUrl(), pendingRoute);
        if (target == null) return;

        pendingRoute = null;
        backExitGuard.reset();
        webView.loadUrl(target);
    }

    private String readServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS_GROUP, MODE_PRIVATE);
        return prefs.getString(SERVER_URL_KEY, null);
    }

    private WebView webView() {
        Bridge bridge = getBridge();
        return bridge == null ? null : bridge.getWebView();
    }

    private void handleBack() {
        // OnBackPressedDispatcher consults the most recently added callback first,
        // so this shadows @capacitor/app's own history-walking callback. That
        // plugin's back handling is disabled in capacitor.config.ts to keep one
        // owner of the rule.
        WebView webView = webView();

        if (webView != null && webView.canGoBack()) {
            backExitGuard.reset();
            webView.goBack();
            return;
        }

        // Monotonic clock: a wall-clock adjustment must not make the delta negative
        // and exit the app on what should only be a re-prompt.
        long now = SystemClock.elapsedRealtime();
        if (backExitGuard.onBackPressed(now) == BackExitGuard.Decision.EXIT) {
            finish();
            return;
        }

        Toast.makeText(this, R.string.press_back_again_to_exit, Toast.LENGTH_SHORT).show();
    }
}
