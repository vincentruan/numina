package app.numina.mobile;

import static org.junit.Assert.assertEquals;

import app.numina.mobile.BackExitGuard.Decision;
import org.junit.Test;

public class BackExitGuardTest {

    /** The requirement's window, asserted literally so a wrong constant cannot pass. */
    private static final long TWO_SECONDS = 2000L;

    @Test
    public void windowIsTwoSeconds() {
        assertEquals(TWO_SECONDS, BackExitGuard.CONFIRM_WINDOW_MS);
    }

    @Test
    public void firstPressPrompts() {
        BackExitGuard guard = new BackExitGuard();
        assertEquals(Decision.PROMPT, guard.onBackPressed(1000L));
    }

    @Test
    public void secondPressWithinWindowExits() {
        BackExitGuard guard = new BackExitGuard();
        guard.onBackPressed(1000L);
        assertEquals(Decision.EXIT, guard.onBackPressed(1000L + TWO_SECONDS - 1));
    }

    @Test
    public void secondPressAtWindowBoundaryPromptsAgain() {
        BackExitGuard guard = new BackExitGuard();
        guard.onBackPressed(1000L);
        assertEquals(Decision.PROMPT, guard.onBackPressed(1000L + TWO_SECONDS));
    }

    @Test
    public void secondPressAfterWindowPromptsAgain() {
        BackExitGuard guard = new BackExitGuard();
        guard.onBackPressed(1000L);
        assertEquals(Decision.PROMPT, guard.onBackPressed(1000L + TWO_SECONDS + 1));
    }

    @Test
    public void lapseThenPressRearmsPrompt() {
        BackExitGuard guard = new BackExitGuard();
        guard.onBackPressed(1000L);
        guard.onBackPressed(1000L + TWO_SECONDS + 1);
        assertEquals(Decision.EXIT, guard.onBackPressed(1000L + TWO_SECONDS + 2));
    }

    @Test
    public void thirdPressAfterExitStartsFresh() {
        BackExitGuard guard = new BackExitGuard();
        guard.onBackPressed(1000L);
        guard.onBackPressed(1500L);
        assertEquals(Decision.PROMPT, guard.onBackPressed(1600L));
    }

    @Test
    public void resetDisarmsPrompt() {
        BackExitGuard guard = new BackExitGuard();
        guard.onBackPressed(1000L);
        guard.reset();
        assertEquals(Decision.PROMPT, guard.onBackPressed(1100L));
    }

    @Test
    public void nonPositiveClockNeverExits() {
        BackExitGuard guard = new BackExitGuard();
        assertEquals(Decision.PROMPT, guard.onBackPressed(0L));
        assertEquals(Decision.PROMPT, guard.onBackPressed(0L));
    }

    @Test
    public void nonPositiveClockAfterArmedPressDoesNotExit() {
        BackExitGuard guard = new BackExitGuard();
        guard.onBackPressed(1000L);
        // A clock reading of 0 would compute -1000 < window and exit; it must not.
        assertEquals(Decision.PROMPT, guard.onBackPressed(0L));
    }
}
