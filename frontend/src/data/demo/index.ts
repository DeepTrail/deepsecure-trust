import ssoLoginData from "./sso-login.json";
import serviceConnectionData from "./service-connection.json";
import agentRegistrationData from "./agent-registration.json";
import delegationData from "./delegation.json";
import mcpToolCallData from "./mcp-tool-call.json";
import auditReviewData from "./audit-review.json";

export interface SceneStep {
  id: string;
  label: string;
  description: string;
  actor: string;
  action: string;
  result?: string;
  metadata?: Record<string, unknown>;
}

export interface SceneData {
  sceneId: string;
  title: string;
  description: string;
  steps: SceneStep[];
}

export const ssoLogin: SceneData = ssoLoginData;
export const serviceConnection: SceneData = serviceConnectionData;
export const agentRegistration: SceneData = agentRegistrationData;
export const delegation: SceneData = delegationData;
export const mcpToolCall: SceneData = mcpToolCallData;
export const auditReview: SceneData = auditReviewData;

export const allScenes: SceneData[] = [
  ssoLogin,
  serviceConnection,
  agentRegistration,
  delegation,
  mcpToolCall,
  auditReview,
];
