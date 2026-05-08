import { describe, it, expect } from "vitest";
import {
  ssoLogin,
  serviceConnection,
  agentRegistration,
  delegation,
  mcpToolCall,
  auditReview,
  allScenes,
  type SceneData,
  type SceneStep,
} from "../index";

const namedScenes = [
  { name: "ssoLogin", data: ssoLogin },
  { name: "serviceConnection", data: serviceConnection },
  { name: "agentRegistration", data: agentRegistration },
  { name: "delegation", data: delegation },
  { name: "mcpToolCall", data: mcpToolCall },
  { name: "auditReview", data: auditReview },
] as const;

describe("Demo Data", () => {
  describe("barrel exports", () => {
    it("exports all 6 named scene data objects", () => {
      expect(ssoLogin).toBeDefined();
      expect(serviceConnection).toBeDefined();
      expect(agentRegistration).toBeDefined();
      expect(delegation).toBeDefined();
      expect(mcpToolCall).toBeDefined();
      expect(auditReview).toBeDefined();
    });

    it("exports allScenes array", () => {
      expect(allScenes).toBeDefined();
      expect(Array.isArray(allScenes)).toBe(true);
    });
  });

  describe("allScenes array", () => {
    it("has exactly 6 entries", () => {
      expect(allScenes).toHaveLength(6);
    });

    it("matches expected scene sequence", () => {
      expect(allScenes[0]).toBe(ssoLogin);
      expect(allScenes[1]).toBe(serviceConnection);
      expect(allScenes[2]).toBe(agentRegistration);
      expect(allScenes[3]).toBe(delegation);
      expect(allScenes[4]).toBe(mcpToolCall);
      expect(allScenes[5]).toBe(auditReview);
    });
  });

  describe.each(namedScenes)("$name — SceneData shape", ({ data }) => {
    it("has required SceneData fields", () => {
      expect(data).toHaveProperty("sceneId");
      expect(data).toHaveProperty("title");
      expect(data).toHaveProperty("description");
      expect(data).toHaveProperty("steps");
      expect(typeof data.sceneId).toBe("string");
      expect(typeof data.title).toBe("string");
      expect(typeof data.description).toBe("string");
      expect(Array.isArray(data.steps)).toBe(true);
      expect(data.steps.length).toBeGreaterThan(0);
    });

    it("has valid SceneStep fields for every step", () => {
      for (const step of data.steps) {
        expect(step).toHaveProperty("id");
        expect(step).toHaveProperty("label");
        expect(step).toHaveProperty("description");
        expect(step).toHaveProperty("actor");
        expect(step).toHaveProperty("action");
        expect(typeof step.id).toBe("string");
        expect(typeof step.label).toBe("string");
        expect(typeof step.description).toBe("string");
        expect(typeof step.actor).toBe("string");
        expect(typeof step.action).toBe("string");
      }
    });

    it("has unique step IDs within the scene", () => {
      const ids = data.steps.map((s: SceneStep) => s.id);
      expect(new Set(ids).size).toBe(ids.length);
    });
  });

  describe("cross-scene uniqueness", () => {
    it("all sceneId values are unique", () => {
      const ids = allScenes.map((s: SceneData) => s.sceneId);
      expect(new Set(ids).size).toBe(ids.length);
    });

    it("has the expected sceneId values", () => {
      const ids = allScenes.map((s: SceneData) => s.sceneId);
      expect(ids).toEqual([
        "sso-login",
        "service-connection",
        "agent-registration",
        "delegation",
        "mcp-tool-call",
        "audit-review",
      ]);
    });
  });

  describe("type compatibility", () => {
    it("SceneData type is structurally compatible", () => {
      const data: SceneData = {
        sceneId: "test",
        title: "Test",
        description: "Test scene",
        steps: [
          {
            id: "t-1",
            label: "Step",
            description: "A step",
            actor: "user",
            action: "do",
          },
        ],
      };
      expect(data.sceneId).toBe("test");
    });

    it("SceneStep accepts optional fields", () => {
      const step: SceneStep = {
        id: "t-1",
        label: "Step",
        description: "A step",
        actor: "user",
        action: "do",
        result: "ok",
        metadata: { key: "value" },
      };
      expect(step.result).toBe("ok");
      expect(step.metadata).toEqual({ key: "value" });
    });
  });
});
