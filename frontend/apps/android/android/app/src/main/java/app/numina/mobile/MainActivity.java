package app.numina.mobile;

import android.content.SharedPreferences;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;

/**
 * Numina Android Shell — thin Capacitor WebView wrapper.
 *
 * <p>On first launch the Capacitor WebView shows the local setup page (server
 * URL configuration). After setup it navigates to the remote Numina H5. From
 * that point on the WebView acts as a browser window: the Android back button
 * walks WebView history, and asks for confirmation before exiting when there
 * is nothing left to go back to.
 *
 * <p>Deep links ({@code numina://open/<path>}) are resolved natively. The route
 * is held until the WebView reports its first page load, so a cold start can
 * finish configuring and loading before the hop.
 */
public class MainActivity extends BridgeActivity {

    /** SharedPreferences file and key written by @capacitor/preferences. */
    private static final String PREFS_GROUP = "CapacitorStorage";
    private static final String SERVER_URL_KEY = "numina_server_url";

    private final BackExitGuard backExitGuard = new BackExitGuard();

    /** Route from a deep link that arrived before the WebView was ready. */
    private String pendingRoute;

    /** Set once the WebView has loaded a page and can accept navigation. */
    private boolean webViewReady;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // BridgeActivity.onCreate() already forwarded the launch intent to
        // onNewIntent(), so the deep link (if any) is captured by then. If the
        // WebView is not ready yet it stays queued until onPageLoaded fires.
        if (getBridge() != null) {
            getBridge().addWebViewListener(new WebViewListener() {
                @Override
                public void onPageLoaded(WebView webView) {
                    webViewReady = true;
                    drainPendingRoute();
                }
            });
        }

        // Predictive back (default for targetSdk 34+) routes back presses
        // through the dispatcher instead of onBackPressed(), so registering
        // here is what keeps the WebView history and exit prompt working.
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

    /** Resolves a launch/resume intent's deep link into a queued or immediate navigation. */
    private void handleDeepLink(Intent intent) {
        if (intent == null) return;
        Uri data = intent.getData();
        if (data == null) return;

        String route = DeepLink.routeFrom(data.toString());
        if (route == null) return;

        pendingRoute = route;
        drainPendingRoute();
    }

    /** Navigates to the queued deep link once a server URL and a loaded WebView exist. */
    private void drainPendingRoute() {
        if (pendingRoute == null || !webViewReady) return;

        WebView webView = getBridge() != null ? getBridge().getWebView() : null;
        if (webView == null) return;

        String target = DeepLink.targetUrl(readServerUrl(), pendingRoute);
        if (target == null) {
            // No server configured yet: keep the route until setup finishes and
            // the remote H5 loads (which re-triggers this via onPageLoaded).
            return;
        }

        pendingRoute = null;
        backExitGuard.reset();
        webView.loadUrl(target);
    }

    /** Reads the same preference the setup page writes via @capacitor/preferences. */
    private String readServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS_GROUP, MODE_PRIVATE);
        String value = prefs.getString(SERVER_URL_KEY, null);
        if (value == null) return null;
        // Trailing slashes would double up when DeepLink joins the route.
        return value.replaceAll("/+$", "");
    }

    /** Back press: walk WebView history, else confirm before exiting. */
    private void handleBack() {
        WebView webView = getBridge() != null ? getBridge().getWebView() : null;

        if (webView != null && webView.canGoBack()) {
            backExitGuard.reset();
            webView.goBack();
            return;
        }

        if (backExitGuard.onBackPressed(System.currentTimeMillis()) == BackExitGuard.Decision.EXIT) {
            finish();
            return;
        }

        Toast.makeText(this, R.string.press_back_again_to_exit, Toast.LENGTH_SHORT).show();
    }
}
