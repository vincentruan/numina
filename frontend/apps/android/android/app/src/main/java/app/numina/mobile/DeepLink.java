package app.numina.mobile;

import java.net.URI;
import java.net.URISyntaxException;

final class DeepLink {

    static final String SCHEME = "numina";
    static final String HOST = "open";

    private DeepLink() {}

    static URI parse(String raw) {
        if (raw == null || raw.isEmpty()) return null;
        try {
            return new URI(raw);
        } catch (URISyntaxException e) {
            return null;
        }
    }

    static boolean isDeepLink(URI uri) {
        if (uri == null) return false;
        if (!SCHEME.equalsIgnoreCase(uri.getScheme())) return false;
        return HOST.equalsIgnoreCase(uri.getHost());
    }

    /**
     * Path (with query and fragment) for {@code numina://open/<path>}. Bare
     * host yields {@code /}. Returns {@code null} when the URI is not a deep
     * link.
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

    static String routeFrom(String raw) {
        return routeFrom(parse(raw));
    }

    static String targetUrl(String serverUrl, String route) {
        if (serverUrl == null || serverUrl.isEmpty()) return null;
        if (route == null || route.isEmpty()) return serverUrl;

        String base = serverUrl.endsWith("/") ? serverUrl.substring(0, serverUrl.length() - 1) : serverUrl;
        String normalizedRoute = route.startsWith("/") ? route : "/" + route;
        return base + normalizedRoute;
    }
}
