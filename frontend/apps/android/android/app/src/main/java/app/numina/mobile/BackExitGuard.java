package app.numina.mobile;

final class BackExitGuard {

    static final long CONFIRM_WINDOW_MS = 2000;

    private long armedAt = 0;

    enum Decision {
        PROMPT,
        EXIT,
    }

    /**
     * A non-positive clock reading is treated as a fresh press so a broken
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

    void reset() {
        armedAt = 0;
    }
}
