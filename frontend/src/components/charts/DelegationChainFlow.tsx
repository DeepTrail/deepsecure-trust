"use client";

import React, { useMemo, useCallback, useState } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  type Node,
  type Edge,
  Position,
  Handle,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { AuditSummary, AvailablePermissionsResponse } from "@/lib/types/audit";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Network } from "lucide-react";

interface Delegation {
  delegation_id: string;
  agent_id: string;
  permissions: string[];
}

interface DelegationChainFlowProps {
  userEmail: string;
  connectedServices: AvailablePermissionsResponse;
  delegations: Delegation[];
  summary: AuditSummary;
  resolve: (id: string) => string;
}

const LAYER_X = [0, 280, 560, 840, 1120];
const NODE_HEIGHT = 80;
const NODE_GAP = 20;

function verticalPositions(count: number): number[] {
  const totalHeight = count * NODE_HEIGHT + (count - 1) * NODE_GAP;
  const startY = -totalHeight / 2;
  return Array.from({ length: count }, (_, i) => startY + i * (NODE_HEIGHT + NODE_GAP));
}

/* ─── Custom Node Components ─── */

function UserNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-blue-400 bg-blue-50 dark:bg-blue-950/40 px-4 py-3 min-w-[160px] text-center shadow-sm">
      <Handle type="source" position={Position.Right} className="!bg-blue-500" />
      <div className="text-[10px] font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-1">User</div>
      <div className="text-xs font-semibold text-blue-900 dark:text-blue-100 truncate">{String(data.label)}</div>
    </div>
  );
}

function ServiceNodeComponent({ data }: { data: Record<string, unknown> }) {
  const inactive = data.inactive as boolean;
  return (
    <div className={`rounded-lg border-2 px-4 py-3 min-w-[140px] text-center shadow-sm ${
      inactive
        ? "border-dashed border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900/40"
        : "border-teal-400 bg-teal-50 dark:bg-teal-950/40"
    }`}>
      <Handle type="target" position={Position.Left} className="!bg-teal-500" />
      <Handle type="source" position={Position.Right} className="!bg-teal-500" />
      <div className="text-[10px] font-medium text-teal-600 dark:text-teal-400 uppercase tracking-wider mb-1">Service</div>
      <div className="text-xs font-semibold text-teal-900 dark:text-teal-100">{String(data.label)}</div>
      <div className="text-[10px] text-teal-700 dark:text-teal-300 mt-0.5">{String(data.scopeCount)} scopes</div>
    </div>
  );
}

function DelegationNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-purple-400 bg-purple-50 dark:bg-purple-950/40 px-4 py-3 min-w-[140px] text-center shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-purple-500" />
      <Handle type="source" position={Position.Right} className="!bg-purple-500" />
      <div className="text-[10px] font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wider mb-1">Delegation</div>
      <div className="text-xs font-semibold text-purple-900 dark:text-purple-100 truncate max-w-[120px] mx-auto">{String(data.label)}</div>
      <div className="text-[10px] text-purple-700 dark:text-purple-300 mt-0.5">{String(data.permCount)} perms</div>
    </div>
  );
}

function AgentNodeComponent({ data }: { data: Record<string, unknown> }) {
  const inactive = data.inactive as boolean;
  return (
    <div className={`rounded-lg border-2 px-4 py-3 min-w-[140px] text-center shadow-sm ${
      inactive
        ? "border-green-300 dark:border-green-700 bg-green-50/50 dark:bg-green-950/20"
        : "border-green-400 bg-green-50 dark:bg-green-950/40"
    }`}>
      <Handle type="target" position={Position.Left} className="!bg-green-500" />
      <Handle type="source" position={Position.Right} className="!bg-green-500" />
      <div className="text-[10px] font-medium text-green-600 dark:text-green-400 uppercase tracking-wider mb-1">Agent</div>
      <div className="text-xs font-semibold text-green-900 dark:text-green-100 truncate max-w-[120px] mx-auto">{String(data.label)}</div>
      {inactive && <div className="text-[10px] text-gray-500 mt-0.5">no activity</div>}
    </div>
  );
}

function ToolNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-amber-400 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 min-w-[160px] text-center shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-amber-500" />
      <div className="text-[10px] font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-1">Tool</div>
      <div className="text-xs font-semibold text-amber-900 dark:text-amber-100 font-mono truncate max-w-[140px] mx-auto">{String(data.label)}</div>
      <div className="text-[10px] text-amber-700 dark:text-amber-300 mt-0.5">{String(data.callCount)} calls</div>
    </div>
  );
}

const nodeTypes = {
  userNode: UserNodeComponent,
  serviceNode: ServiceNodeComponent,
  delegationNode: DelegationNodeComponent,
  agentNode: AgentNodeComponent,
  toolNode: ToolNodeComponent,
};

export default function DelegationChainFlow({
  userEmail,
  connectedServices,
  delegations,
  summary,
  resolve,
}: DelegationChainFlowProps) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const { nodes, edges } = useMemo(() => {
    const allNodes: Node[] = [];
    const allEdges: Edge[] = [];

    // Layer 1: User
    allNodes.push({
      id: "user-root",
      type: "userNode",
      position: { x: LAYER_X[0], y: 0 },
      data: { label: userEmail },
    });

    // Layer 2: Connected Services
    const serviceEntries = Object.entries(connectedServices.services);
    const serviceYPositions = verticalPositions(serviceEntries.length);
    const serviceIdMap = new Map<string, string>();

    serviceEntries.forEach(([serviceId, svc], i) => {
      const nodeId = `svc-${serviceId}`;
      serviceIdMap.set(serviceId, nodeId);

      const hasDelegation = delegations.some((d) =>
        d.permissions.some((p) => p.startsWith(`${serviceId}:`))
      );

      allNodes.push({
        id: nodeId,
        type: "serviceNode",
        position: { x: LAYER_X[1], y: serviceYPositions[i] },
        data: {
          label: svc.service_name || serviceId,
          scopeCount: svc.scopes_granted.length,
          inactive: !hasDelegation,
        },
      });

      allEdges.push({
        id: `user-to-${nodeId}`,
        source: "user-root",
        target: nodeId,
        type: "smoothstep",
        animated: hasDelegation,
        style: hasDelegation ? { stroke: "#14b8a6" } : { stroke: "#d1d5db", strokeDasharray: "5 5" },
      });
    });

    // Layer 3: Delegations
    const delYPositions = verticalPositions(delegations.length);
    const delegationServiceLinks = new Map<string, Set<string>>();

    delegations.forEach((d, i) => {
      const nodeId = `del-${d.delegation_id}`;
      const truncatedId = d.delegation_id.length > 14 ? `${d.delegation_id.slice(0, 14)}...` : d.delegation_id;
      const serviceSet = new Set<string>();

      d.permissions.forEach((p) => {
        const svcPrefix = p.split(":")[0];
        serviceSet.add(svcPrefix);
      });
      delegationServiceLinks.set(d.delegation_id, serviceSet);

      allNodes.push({
        id: nodeId,
        type: "delegationNode",
        position: { x: LAYER_X[2], y: delYPositions[i] },
        data: { label: truncatedId, permCount: d.permissions.length },
      });

      // Edges: Service -> Delegation
      serviceSet.forEach((svcPrefix) => {
        const svcNodeId = serviceIdMap.get(svcPrefix);
        if (svcNodeId) {
          const permCount = d.permissions.filter((p) => p.startsWith(`${svcPrefix}:`)).length;
          allEdges.push({
            id: `${svcNodeId}-to-${nodeId}`,
            source: svcNodeId,
            target: nodeId,
            type: "smoothstep",
            animated: true,
            label: `${permCount} perm${permCount !== 1 ? "s" : ""}`,
            labelStyle: { fontSize: 9, fill: "#a855f7" },
            style: { stroke: "#a855f7" },
          });
        }
      });
    });

    // Layer 4: Agents (deduplicate — multiple delegations can target the same agent)
    const agentIds = [...new Set(delegations.map((d) => d.agent_id))];
    const agentYPositions = verticalPositions(agentIds.length);

    const toolsByAgent = new Map<string, string[]>();
    for (const [tool] of Object.entries(summary.by_tool)) {
      const toolService = tool.split(".")[0];
      for (const agentId of agentIds) {
        const agentDelegations = delegations.filter((d) => d.agent_id === agentId);
        const hasMatchingPermission = agentDelegations.some((d) =>
          d.permissions.some((p) => p.startsWith(`${toolService}:`))
        );
        if (hasMatchingPermission) {
          const existing = toolsByAgent.get(agentId) ?? [];
          if (!existing.includes(tool)) {
            toolsByAgent.set(agentId, [...existing, tool]);
          }
        }
      }
    }

    agentIds.forEach((agentId, i) => {
      const nodeId = `agent-${agentId}`;
      const agentTools = toolsByAgent.get(agentId) ?? [];
      const hasActivity = agentTools.length > 0;

      allNodes.push({
        id: nodeId,
        type: "agentNode",
        position: { x: LAYER_X[3], y: agentYPositions[i] },
        data: { label: resolve(agentId), inactive: !hasActivity },
      });

      // Edges: Delegation -> Agent
      delegations
        .filter((d) => d.agent_id === agentId)
        .forEach((d) => {
          allEdges.push({
            id: `del-${d.delegation_id}-to-${nodeId}`,
            source: `del-${d.delegation_id}`,
            target: nodeId,
            type: "smoothstep",
            animated: hasActivity,
            style: hasActivity ? { stroke: "#22c55e" } : { stroke: "#d1d5db", strokeDasharray: "5 5" },
          });
        });
    });

    // Layer 5: Tools
    const toolEntries = Object.entries(summary.by_tool);
    const toolYPositions = verticalPositions(toolEntries.length);

    toolEntries.forEach(([tool, count], i) => {
      const nodeId = `tool-${tool}`;
      allNodes.push({
        id: nodeId,
        type: "toolNode",
        position: { x: LAYER_X[4], y: toolYPositions[i] },
        data: { label: tool, callCount: count },
      });

      // Edges: Agent -> Tool
      const toolService = tool.split(".")[0];
      for (const agentId of agentIds) {
        const agentDelegations = delegations.filter((d) => d.agent_id === agentId);
        const hasPermission = agentDelegations.some((d) =>
          d.permissions.some((p) => p.startsWith(`${toolService}:`))
        );
        if (hasPermission) {
          allEdges.push({
            id: `agent-${agentId}-to-${nodeId}`,
            source: `agent-${agentId}`,
            target: nodeId,
            type: "smoothstep",
            animated: true,
            style: { stroke: "#f59e0b" },
          });
        }
      }
    });

    return { nodes: allNodes, edges: allEdges };
  }, [userEmail, connectedServices, delegations, summary, resolve]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode((prev) => (prev === node.id ? null : node.id));
  }, []);

  const highlightedEdges = useMemo(() => {
    if (!selectedNode) return edges;

    const connected = new Set<string>();
    connected.add(selectedNode);

    // Traverse downstream
    let frontier = [selectedNode];
    while (frontier.length > 0) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const e of edges) {
          if (e.source === id && !connected.has(e.target)) {
            connected.add(e.target);
            next.push(e.target);
          }
        }
      }
      frontier = next;
    }

    // Traverse upstream
    frontier = [selectedNode];
    while (frontier.length > 0) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const e of edges) {
          if (e.target === id && !connected.has(e.source)) {
            connected.add(e.source);
            next.push(e.source);
          }
        }
      }
      frontier = next;
    }

    return edges.map((e) => {
      const isHighlighted = connected.has(e.source) && connected.has(e.target);
      return {
        ...e,
        style: {
          ...e.style,
          opacity: isHighlighted ? 1 : 0.15,
          strokeWidth: isHighlighted ? 2 : 1,
        },
      };
    });
  }, [edges, selectedNode]);

  const highlightedNodes = useMemo(() => {
    if (!selectedNode) return nodes;

    const connected = new Set<string>();
    connected.add(selectedNode);

    let frontier = [selectedNode];
    while (frontier.length > 0) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const e of edges) {
          if (e.source === id && !connected.has(e.target)) {
            connected.add(e.target);
            next.push(e.target);
          }
        }
      }
      frontier = next;
    }

    frontier = [selectedNode];
    while (frontier.length > 0) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const e of edges) {
          if (e.target === id && !connected.has(e.source)) {
            connected.add(e.source);
            next.push(e.source);
          }
        }
      }
      frontier = next;
    }

    return nodes.map((n) => ({
      ...n,
      style: {
        ...n.style,
        opacity: connected.has(n.id) ? 1 : 0.25,
      },
    }));
  }, [nodes, edges, selectedNode]);

  const hasData =
    Object.keys(connectedServices.services).length > 0 ||
    delegations.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Network className="h-4 w-4" />
          Delegation Chain
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!hasData ? (
          <EmptyState
            title="No chain data"
            description="Connect services and create delegations to see the permission chain."
          />
        ) : (
          <div className="h-[450px] w-full rounded-md border bg-background" data-testid="delegation-chain-flow">
            <ReactFlow
              nodes={highlightedNodes}
              edges={highlightedEdges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              onPaneClick={() => setSelectedNode(null)}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={true}
              minZoom={0.3}
              maxZoom={1.5}
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
              <Controls showInteractive={false} />
              <MiniMap
                nodeStrokeWidth={3}
                pannable
                zoomable
              />
            </ReactFlow>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
