import { test as base, type Page } from "@playwright/test";

/**
 * Authenticated page fixture for dashboard E2E tests.
 *
 * Sets a mock `__session` cookie so the Next.js middleware
 * allows access to dashboard routes without a real IdP.
 * The cookie value is an opaque token — the middleware only
 * checks for the cookie's existence, not its contents.
 */
export const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page, context }, use) => {
    await context.addCookies([
      {
        name: "__session",
        value: "mock-session-token-for-e2e",
        domain: "localhost",
        path: "/",
        httpOnly: true,
        secure: false,
        sameSite: "Lax",
      },
    ]);
    await use(page);
  },
});

export { expect } from "@playwright/test";
