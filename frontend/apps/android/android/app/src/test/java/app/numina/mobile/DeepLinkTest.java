package app.numina.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.net.URI;
import org.junit.Test;

public class DeepLinkTest {

    @Test
    public void isDeepLink_acceptsNuminaOpenScheme() {
        assertTrue(DeepLink.isDeepLink(URI.create("numina://open/reminders")));
    }

    @Test
    public void isDeepLink_acceptsSchemeCaseInsensitively() {
        assertTrue(DeepLink.isDeepLink(URI.create("NUMINA://OPEN/reminders")));
    }

    @Test
    public void isDeepLink_rejectsOtherSchemes() {
        assertFalse(DeepLink.isDeepLink(URI.create("https://numina.example.com/reminders")));
    }

    @Test
    public void isDeepLink_rejectsOtherHosts() {
        assertFalse(DeepLink.isDeepLink(URI.create("numina://other/reminders")));
    }

    @Test
    public void isDeepLink_rejectsNull() {
        assertFalse(DeepLink.isDeepLink(null));
    }

    @Test
    public void routeFrom_extractsPath() {
        assertEquals("/reminders", DeepLink.routeFrom(URI.create("numina://open/reminders")));
    }

    @Test
    public void routeFrom_extractsNestedPath() {
        assertEquals(
            "/ai/chat/thread_123", DeepLink.routeFrom(URI.create("numina://open/ai/chat/thread_123"))
        );
    }

    @Test
    public void routeFrom_bareHostYieldsRoot() {
        assertEquals("/", DeepLink.routeFrom(URI.create("numina://open")));
    }

    @Test
    public void routeFrom_trailingSlashYieldsRoot() {
        assertEquals("/", DeepLink.routeFrom(URI.create("numina://open/")));
    }

    @Test
    public void routeFrom_preservesQuery() {
        assertEquals("/reminders?tab=due", DeepLink.routeFrom(URI.create("numina://open/reminders?tab=due")));
    }

    @Test
    public void routeFrom_preservesFragment() {
        assertEquals("/reminders#top", DeepLink.routeFrom(URI.create("numina://open/reminders#top")));
    }

    @Test
    public void routeFrom_returnsNullForNonDeepLink() {
        assertNull(DeepLink.routeFrom(URI.create("https://example.com/reminders")));
    }

    @Test
    public void routeFrom_returnsNullForMalformedInput() {
        assertNull(DeepLink.routeFrom("numina://open/space here"));
    }

    @Test
    public void routeFrom_returnsNullForNull() {
        assertNull(DeepLink.routeFrom((String) null));
    }

    @Test
    public void targetUrl_joinsServerAndRoute() {
        assertEquals(
            "https://numina.example.com/reminders",
            DeepLink.targetUrl("https://numina.example.com", "/reminders")
        );
    }

    @Test
    public void targetUrl_stripsTrailingSlashFromServer() {
        assertEquals(
            "https://numina.example.com/reminders",
            DeepLink.targetUrl("https://numina.example.com/", "/reminders")
        );
    }

    @Test
    public void targetUrl_addsLeadingSlashToRoute() {
        assertEquals(
            "https://numina.example.com/reminders",
            DeepLink.targetUrl("https://numina.example.com", "reminders")
        );
    }

    @Test
    public void targetUrl_rootRouteYieldsServerRoot() {
        assertEquals("https://numina.example.com/", DeepLink.targetUrl("https://numina.example.com", "/"));
    }

    @Test
    public void targetUrl_nullWhenNoServerConfigured() {
        assertNull(DeepLink.targetUrl(null, "/reminders"));
        assertNull(DeepLink.targetUrl("", "/reminders"));
    }
}
