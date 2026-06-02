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

/* ─── Monochrome Node Components ─── */

function ServiceNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-foreground/70 bg-background px-4 py-3 min-w-[140px] text-center shadow-sm">
      <Handle type="source" position={Position.Right} className="!bg-foreground !w-2 !h-2" />
      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Service</div>
      <div className="text-xs font-semibold text-foreground">{String(data.label)}</div>
      <div className="text-[10px] text-muted-foreground mt-0.5">{String(data.scopeCount)} scopes</div>
    </div>
  );
}

function UserNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-foreground bg-background px-4 py-3 min-w-[160px] text-center shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-foreground !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-foreground !w-2 !h-2" />
      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">User</div>
      <div className="text-xs font-semibold text-foreground truncate">{String(data.label)}</div>
    </div>
  );
}

function DelegationNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-foreground/50 bg-muted/40 px-4 py-3 min-w-[140px] text-center shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-foreground !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-foreground !w-2 !h-2" />
      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Delegation</div>
      <div className="text-xs font-semibold text-foreground truncate max-w-[120px] mx-auto">{String(data.label)}</div>
      <div className="text-[10px] text-muted-foreground mt-0.5">{String(data.permCount)} perms</div>
    </div>
  );
}

function AgentNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-foreground/70 bg-background px-4 py-3 min-w-[140px] text-center shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-foreground !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-foreground !w-2 !h-2" />
      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Agent</div>
      <div className="text-xs font-semibold text-foreground truncate max-w-[120px] mx-auto">{String(data.label)}</div>
    </div>
  );
}

function ToolNodeComponent({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg border-2 border-foreground bg-background px-4 py-3 min-w-[160px] text-center shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-foreground !w-2 !h-2" />
      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Tool</div>
      <div className="text-xs font-semibold text-foreground font-mono truncate max-w-[140px] mx-auto">{String(data.label)}</div>
      <div className="text-[10px] text-muted-foreground mt-0.5">{String(data.callCount)} calls</div>
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

const EDGE_COLOR = "hsl(0 0% 25%)";
const EDGE_WIDTH = 2.5;

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

    // Layer 0: Connected Services
    const serviceEntries = Object.entries(connectedServices.services);
    const serviceYPositions = verticalPositions(serviceEntries.length);

    serviceEntries.forEach(([serviceId, svc], i) => {
      const nodeId = `svc-${serviceId}`;
      allNodes.push({
        id: nodeId,
        type: "serviceNode",
        position: { x: LAYER_X[0], y: serviceYPositions[i] },
        data: {
          label: svc.service_name || serviceId,
          scopeCount: svc.scopes_granted.length,
        },
      });
    });

    // Layer 1: User (centered vertically)
    allNodes.push({
      id: "user-root",
      type: "userNode",
      position: { x: LAYER_X[1], y: 0 },
      data: { label: userEmail },
    });

    // Edges: Service → User (all connected services feed into the user)
    serviceEntries.forEach(([serviceId]) => {
      const svcNodeId = `svc-${serviceId}`;
      allEdges.push({
        id: `${svcNodeId}-to-user`,
        source: svcNodeId,
        target: "user-root",
        type: "smoothstep",
        animated: true,
        style: { stroke: EDGE_COLOR, strokeWidth: EDGE_WIDTH },
      });
    });

    // Layer 2: Delegations (created by user)
    const delYPositions = verticalPositions(delegations.length);

    delegations.forEach((d, i) => {
      const nodeId = `del-${d.delegation_id}`;
      const truncatedId = d.delegation_id.length > 14 ? `${d.delegation_id.slice(0, 14)}...` : d.delegation_id;

      allNodes.push({
        id: nodeId,
        type: "delegationNode",
        position: { x: LAYER_X[2], y: delYPositions[i] },
        data: { label: truncatedId, permCount: d.permissions.length },
      });

      // Edge: User → Delegation
      allEdges.push({
        id: `user-to-${nodeId}`,
        source: "user-root",
        target: nodeId,
        type: "smoothstep",
        animated: true,
        label: `${d.permissions.length} perm${d.permissions.length !== 1 ? "s" : ""}`,
        labelStyle: { fontSize: 9, fill: "hsl(0 0% 45%)" },
        style: { stroke: EDGE_COLOR, strokeWidth: EDGE_WIDTH },
      });
    });

    // Layer 3: Agents (deduplicated)
    const agentIds = [...new Set(delegations.map((d) => d.agent_id))];
    const agentYPositions = verticalPositions(agentIds.length);

    agentIds.forEach((agentId, i) => {
      const nodeId = `agent-${agentId}`;

      allNodes.push({
        id: nodeId,
        type: "agentNode",
        position: { x: LAYER_X[3], y: agentYPositions[i] },
        data: { label: resolve(agentId) },
      });

      // Edges: Delegation → Agent
      delegations
        .filter((d) => d.agent_id === agentId)
        .forEach((d) => {
          allEdges.push({
            id: `del-${d.delegation_id}-to-${nodeId}`,
            source: `del-${d.delegation_id}`,
            target: nodeId,
            type: "smoothstep",
            animated: true,
            style: { stroke: EDGE_COLOR, strokeWidth: EDGE_WIDTH },
          });
        });
    });

    // Layer 4: Tools
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

      // Edges: Agent → Tool (based on permission match)
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
            style: { stroke: EDGE_COLOR, strokeWidth: EDGE_WIDTH },
          });
        }
      }
    });

    return { nodes: allNodes, edges: allEdges };
  }, [userEmail, connectedServices, delegations, summary, resolve]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode((prev) => (prev === node.id ? null : node.id));
  }, []);

  const connectedNodeIds = useMemo(() => {
    if (!selectedNode) return null;

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

    return connected;
  }, [selectedNode, edges]);

  const highlightedEdges = useMemo(() => {
    if (!connectedNodeIds) return edges;

    return edges.map((e) => {
      const isHighlighted = connectedNodeIds.has(e.source) && connectedNodeIds.has(e.target);
      return {
        ...e,
        style: {
          ...e.style,
          opacity: isHighlighted ? 1 : 0.12,
          strokeWidth: isHighlighted ? 3 : 1,
        },
        animated: isHighlighted,
      };
    });
  }, [edges, connectedNodeIds]);

  const highlightedNodes = useMemo(() => {
    if (!connectedNodeIds) return nodes;

    return nodes.map((n) => ({
      ...n,
      style: {
        ...n.style,
        opacity: connectedNodeIds.has(n.id) ? 1 : 0.2,
      },
    }));
  }, [nodes, connectedNodeIds]);

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
              <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="hsl(0 0% 85%)" />
              <Controls showInteractive={false} />
              <MiniMap
                nodeStrokeWidth={3}
                pannable
                zoomable
                nodeColor={() => "hsl(0 0% 90%)"}
                nodeStrokeColor={() => "hsl(0 0% 40%)"}
              />
            </ReactFlow>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
