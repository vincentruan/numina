package app.numina.mobile;

import java.net.URI;
import java.net.URISyntaxException;

/**
 * Pure helpers for the shell's deep-link handling.
 *
 * <p>Kept free of Android framework state (no Activity, no WebView, no
 * android.net.Uri) so the URL translation rules run in plain JVM unit tests.
 * {@link MainActivity} owns the lifecycle and WebView interaction; this class
 * only decides *what* the target URL should be.
 */
final class DeepLink {

    /** Scheme and host of the app's deep links: {@code numina://open/<path>}. */
    static final String SCHEME = "numina";
    static final String HOST = "open";

    private DeepLink() {}

    /** Parses a raw URI string, returning {@code null} when it is malformed. */
    static URI parse(String raw) {
        if (raw == null || raw.isEmpty()) return null;
        try {
            return new URI(raw);
        } catch (URISyntaxException e) {
            return null;
        }
    }

    /** Returns whether {@code uri} is one of this app's deep links. */
    static boolean isDeepLink(URI uri) {
        if (uri == null) return false;
        if (!SCHEME.equalsIgnoreCase(uri.getScheme())) return false;
        return HOST.equalsIgnoreCase(uri.getHost());
    }

    /**
     * Extracts the in-app route from a deep link.
     *
     * <p>{@code numina://open/reminders} becomes {@code /reminders}. The host
     * segment is not part of the route, so it is never included. A deep link
     * with no path ({@code numina://open} or {@code numina://open/}) yields
     * {@code /}, which the caller resolves to the server root.
     *
     * <p>Query and fragment are preserved so routes carrying state survive the
     * hop.
     *
     * @return a path always beginning with {@code /}, or {@code null} when the
     *     URI is not a deep link and should be ignored
     */
    static String routeFrom(URI uri) {
        if (!isDeepLink(uri)) return null;

        String path = uri.getPath();
        if (path == null || path.isEmpty()) path = "/";

        StringBuilder route = new StringBuilder(path);
        String query = uri.getQuery();
        if (query != null && !query.isEmpty()) route.append('?').append(query);
        String fragment = uri.getFragment();
        if (fragment != null && !fragment.isEmpty()) route.append('#').append(fragment);
        return route.toString();
    }

    /** Convenience overload: parse then extract, returning null on either failure. */
    static String routeFrom(String raw) {
        return routeFrom(parse(raw));
    }

    /**
     * Builds the absolute URL the WebView should load for a deep link route.
     *
     * <p>Returns {@code null} when no server is configured yet; the route must
     * then be held until setup completes.
     */
    static String targetUrl(String serverUrl, String route) {
        if (serverUrl == null || serverUrl.isEmpty()) return null;
        if (route == null || route.isEmpty()) return serverUrl;

        String base = serverUrl.endsWith("/") ? serverUrl.substring(0, serverUrl.length() - 1) : serverUrl;
        String normalizedRoute = route.startsWith("/") ? route : "/" + route;
        return base + normalizedRoute;
    }
}
