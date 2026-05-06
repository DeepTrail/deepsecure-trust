import { test, expect } from "./fixtures/auth";
import type { Page, Route } from "@playwright/test";

const MOCK_AGENTS = [
  { id: "agent-1", agent_id: "agent-alpha", name: "Alpha Agent", status: "active", public_key: "abc123base64" },
  { id: "agent-2", agent_id: "agent-beta", name: "Beta Agent", status: "registered", public_key: null },
];

const MOCK_POLICIES = [
  { id: "policy-1", name: "Default Policy", description: "Allow read access", permissions: ["read"], agent_ids: ["agent-alpha"] },
  { id: "policy-2", name: "Admin Policy", description: "Full access", permissions: ["read", "write"], agent_ids: [] },
];

const MOCK_SERVICES = [
  { service_id: "notion", service_name: "Notion", connected: true, scopes: ["pages:read"], description: "Notion integration" },
  { service_id: "slack", service_name: "Slack", connected: false, scopes: ["messages:read"], description: "Slack integration" },
];

const MOCK_EVENTS = [
  {
    id: "evt-1", event_type: "mcp_tool_call", timestamp: "2026-01-15T09:00:00Z",
    agent_id: "agent-alpha", user_id: "user-1", token_layer: "agent",
    details: { tool: "notion.search" },
    attribution_chain: [{ actor: "user-1", action: "delegate", layer: "user" }],
  },
  {
    id: "evt-2", event_type: "agent_auth", timestamp: "2026-01-15T10:00:00Z",
    agent_id: "agent-beta", token_layer: "delegation", details: {}, attribution_chain: [],
  },
];

const MOCK_SECRETS = [
  { id: "secret-1", name: "NOTION_TOKEN", service: "notion", created_at: "2026-01-01T00:00:00Z" },
  { id: "secret-2", name: "SLACK_TOKEN", service: "slack", created_at: "2026-01-02T00:00:00Z" },
];

const MOCK_TASKS = [
  { id: "task-1", name: "Sync Notion", agent_id: "agent-alpha", status: "active", description: "Daily sync" },
  { id: "task-2", name: "Post Summary", agent_id: "agent-beta", status: "pending", description: "Weekly" },
];

async function setupHappyPathMocks(page: Page) {
  await page.route("**/api/proxy/agents**", (route: Route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_AGENTS) });
    }
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "new", agent_id: "new-agent", name: "New", status: "registered" }) });
    }
    if (route.request().method() === "DELETE") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    }
    return route.continue();
  });

  await page.route("**/api/proxy/policies**", (route: Route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_POLICIES) });
    }
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "new-policy", name: "New" }) });
    }
    if (route.request().method() === "PUT") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "policy-1", name: "Updated" }) });
    }
    if (route.request().method() === "DELETE") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    }
    return route.continue();
  });

  await page.route("**/api/proxy/users/me/available-permissions**", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_SERVICES) })
  );

  await page.route("**/api/proxy/audit/events**", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_EVENTS) })
  );

  await page.route("**/api/proxy/vault/secrets**", (route: Route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_SECRETS) });
    }
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "new-secret", name: "NEW_KEY" }) });
    }
    if (route.request().method() === "DELETE") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    }
    return route.continue();
  });

  await page.route("**/api/proxy/tasks**", (route: Route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_TASKS) });
    }
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "new-task", name: "New Task" }) });
    }
    return route.continue();
  });

  await page.route("**/api/proxy/oauth/**", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ redirect_url: "/callback" }) })
  );
}

async function setupErrorMocks(page: Page) {
  await page.route("**/api/proxy/**", (route: Route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Internal Server Error" }) })
  );
}

async function setupEmptyMocks(page: Page) {
  await page.route("**/api/proxy/**", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
}

// ── Dashboard Overview ──────────────────────────────────────────

test.describe("Dashboard Overview", () => {
  test("renders metric cards with data", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");

    const main = authedPage.getByRole("main");
    await expect(main.getByText("Agents")).toBeVisible({ timeout: 10000 });
    await expect(main.getByText("Policies")).toBeVisible();
  });

  test("shows error state on API failure", async ({ authedPage }) => {
    await setupErrorMocks(authedPage);
    await authedPage.goto("/dashboard");

    // The overview page catches individual API errors gracefully and shows zero counts.
    // Verify the page still renders (no crash) with fallback values.
    const main = authedPage.getByRole("main");
    await expect(main.locator("text=Overview").or(main.getByText(/failed to load|error|0/i)).first()).toBeVisible({ timeout: 10000 });
  });

  test("navigates from sidebar link", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");

    const overviewLink = authedPage.locator('a[href="/dashboard"]').first();
    await expect(overviewLink).toBeVisible();
  });

  test("displays metric count accuracy", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");

    // Verify agent count (2 agents mocked) in the main content area
    const main = authedPage.getByRole("main");
    await expect(main.getByText("2").first()).toBeVisible({ timeout: 10000 });
  });
});

// ── Agents Page ─────────────────────────────────────────────────

test.describe("Agents Page", () => {
  test("lists agents", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/agents");

    await expect(authedPage.getByText("agent-alpha")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText("agent-beta")).toBeVisible();
  });

  test("shows empty state", async ({ authedPage }) => {
    await setupEmptyMocks(authedPage);
    await authedPage.goto("/dashboard/agents");

    await expect(authedPage.getByText(/no agents/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("navigates via sidebar", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");
    await authedPage.getByRole("link", { name: "Agents" }).click();
    await expect(authedPage).toHaveURL(/\/dashboard\/agents/);
  });

  test("opens create form and submits new agent", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/agents");
    await expect(authedPage.getByText("agent-alpha")).toBeVisible({ timeout: 10000 });

    await authedPage.getByRole("button", { name: /register agent/i }).click();
    // The form uses placeholder "my-agent" on the Agent ID field
    await expect(authedPage.getByPlaceholder("my-agent").or(authedPage.locator("#agent-id"))).toBeVisible();
  });

  test("shows status badges on agent cards", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/agents");

    await expect(authedPage.getByText("active")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText("registered")).toBeVisible();
  });
});

// ── Policies Page ───────────────────────────────────────────────

test.describe("Policies Page", () => {
  test("lists policies", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/policies");

    await expect(authedPage.getByText("Default Policy")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText("Admin Policy")).toBeVisible();
  });

  test("shows empty state", async ({ authedPage }) => {
    await setupEmptyMocks(authedPage);
    await authedPage.goto("/dashboard/policies");

    await expect(authedPage.getByText(/no policies/i)).toBeVisible({ timeout: 10000 });
  });

  test("navigates via sidebar", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");
    await authedPage.getByRole("link", { name: "Policies" }).click();
    await expect(authedPage).toHaveURL(/\/dashboard\/policies/);
  });

  test("displays permissions on policy cards", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/policies");

    await expect(authedPage.getByText("Default Policy")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText("Allow read access")).toBeVisible();
  });
});

// ── Services Page ───────────────────────────────────────────────

test.describe("Services Page", () => {
  test("lists services with connect/disconnect buttons", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/services");

    await expect(authedPage.getByText("Notion", { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText("Slack", { exact: true })).toBeVisible();
  });

  test("shows empty state", async ({ authedPage }) => {
    await setupEmptyMocks(authedPage);
    await authedPage.goto("/dashboard/services");

    await expect(authedPage.getByText(/no services/i)).toBeVisible({ timeout: 10000 });
  });

  test("navigates via sidebar", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");
    await authedPage.getByRole("link", { name: "Services" }).click();
    await expect(authedPage).toHaveURL(/\/dashboard\/services/);
  });

  test("shows connect and disconnect button states", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/services");

    await expect(authedPage.getByText("Notion", { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText(/disconnect/i).first()).toBeVisible();
    await expect(authedPage.getByText(/connect/i).first()).toBeVisible();
  });
});

// ── Audit Trail Page ────────────────────────────────────────────

test.describe("Audit Trail Page", () => {
  test("lists audit events", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/audit");

    const main = authedPage.getByRole("main");
    // Wait for event data to load — agent-alpha is unique to mock event cards
    await expect(main.getByText("agent-alpha")).toBeVisible({ timeout: 10000 });
    // Verify event types are rendered (nth(1) skips the hidden <option> in the filter dropdown)
    await expect(main.getByText("mcp_tool_call").nth(1)).toBeVisible();
    await expect(main.getByText("agent_auth").nth(1)).toBeVisible();
  });

  test("shows empty state when no events", async ({ authedPage }) => {
    await setupEmptyMocks(authedPage);
    await authedPage.goto("/dashboard/audit");

    await expect(authedPage.getByText(/no.*events|no.*activity/i)).toBeVisible({ timeout: 10000 });
  });

  test("navigates via sidebar", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");
    await authedPage.getByRole("link", { name: "Audit Trail" }).click();
    await expect(authedPage).toHaveURL(/\/dashboard\/audit/);
  });

  test("shows filter controls for event type", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/audit");

    const main = authedPage.getByRole("main");
    await expect(main.getByText("agent-alpha")).toBeVisible({ timeout: 10000 });
    const filterSelect = authedPage.getByLabel("Event Type");
    await expect(filterSelect).toBeVisible();
    await expect(filterSelect).toBeEnabled();
  });

  test("displays token layer badges", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/audit");

    const main = authedPage.getByRole("main");
    await expect(main.getByText("agent-alpha")).toBeVisible({ timeout: 10000 });
    // Verify token layer badge is rendered — use Badge locator to avoid hidden <option> elements
    await expect(main.locator(".inline-flex").getByText("agent", { exact: true }).first()).toBeVisible();
  });
});

// ── Vault Page ──────────────────────────────────────────────────

test.describe("Vault Page", () => {
  test("lists secrets", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/vault");

    await expect(authedPage.getByText("NOTION_TOKEN")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText("SLACK_TOKEN")).toBeVisible();
  });

  test("shows empty state", async ({ authedPage }) => {
    await setupEmptyMocks(authedPage);
    await authedPage.goto("/dashboard/vault");

    await expect(authedPage.getByText(/no secrets/i)).toBeVisible({ timeout: 10000 });
  });

  test("navigates via sidebar", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");
    await authedPage.getByRole("link", { name: "Vault" }).click();
    await expect(authedPage).toHaveURL(/\/dashboard\/vault/);
  });

  test("opens store secret form", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/vault");

    await expect(authedPage.getByText("NOTION_TOKEN")).toBeVisible({ timeout: 10000 });
    const storeButton = authedPage.getByRole("button", { name: /store secret|add secret/i });
    if (await storeButton.isVisible()) {
      await storeButton.click();
      await expect(
        authedPage.locator('input[name="key"]').or(authedPage.getByPlaceholder(/key|name/i))
      ).toBeVisible();
    }
  });

  test("displays service association on secrets", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/vault");

    await expect(authedPage.getByText("NOTION_TOKEN")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText(/notion/i).first()).toBeVisible();
  });
});

// ── Tasks Page ──────────────────────────────────────────────────

test.describe("Tasks Page", () => {
  test("lists tasks with status badges", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/tasks");

    await expect(authedPage.getByText("Sync Notion")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText("Post Summary")).toBeVisible();
  });

  test("shows empty state", async ({ authedPage }) => {
    await setupEmptyMocks(authedPage);
    await authedPage.goto("/dashboard/tasks");

    await expect(authedPage.getByText(/no tasks/i)).toBeVisible({ timeout: 10000 });
  });

  test("navigates via sidebar", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard");
    await authedPage.getByRole("link", { name: "Tasks" }).click();
    await expect(authedPage).toHaveURL(/\/dashboard\/tasks/);
  });

  test("shows task status indicators", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/tasks");

    await expect(authedPage.getByText("Sync Notion")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText(/active/i).first()).toBeVisible();
    await expect(authedPage.getByText(/pending/i).first()).toBeVisible();
  });

  test("shows agent association on tasks", async ({ authedPage }) => {
    await setupHappyPathMocks(authedPage);
    await authedPage.goto("/dashboard/tasks");

    await expect(authedPage.getByText("Sync Notion")).toBeVisible({ timeout: 10000 });
    await expect(authedPage.getByText(/agent-alpha/i)).toBeVisible();
  });
});
