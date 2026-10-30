package app.numina.mobile;

/**
 * Back-button exit confirmation state.
 *
 * <p>Pressing back when there is no WebView history should not exit the app
 * immediately — on Android a stray press would drop the user out of a
 * long-lived session. Instead the first press asks for confirmation and a
 * second press inside the window exits.
 *
 * <p>Kept as a plain class so the timing rule is unit-testable without an
 * emulator: {@link MainActivity} supplies the clock and reacts to the result.
 */
final class BackExitGuard {

    /** How long the "press again to exit" prompt stays armed. */
    static final long CONFIRM_WINDOW_MS = 2000;

    /** Clock value of the last press that armed the prompt; 0 when disarmed. */
    private long armedAt = 0;

    enum Decision {
        /** No prompt was armed, or the window lapsed: ask for confirmation. */
        PROMPT,
        /** The prompt was still armed: exit the app. */
        EXIT,
    }

    /**
     * Records a back press at {@code nowMs} and returns what should happen.
     *
     * <p>A non-positive clock reading is treated as a fresh press so a broken
     * clock can never silently exit without ever showing the prompt.
     */
    Decision onBackPressed(long nowMs) {
        if (nowMs > 0 && armedAt > 0 && nowMs - armedAt < CONFIRM_WINDOW_MS) {
            armedAt = 0;
            return Decision.EXIT;
        }
        armedAt = nowMs;
        return Decision.PROMPT;
    }

    /** Clears the armed prompt, e.g. when the WebView gains history again. */
    void reset() {
        armedAt = 0;
    }
}
