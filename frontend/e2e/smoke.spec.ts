import { test, expect } from "@playwright/test";

test("landing page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/DeepSecure/);
});

test("status page returns ok", async ({ page }) => {
  const response = await page.goto("/status");
  expect(response?.status()).toBe(200);
});

test("unauthenticated dashboard redirects to login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
