"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { apiClient } from "@/lib/api/client";

interface Agent {
  agent_id: string;
  name: string;
}

interface UseAgentNamesReturn {
  names: Map<string, string>;
  loading: boolean;
  resolve: (agentId: string) => string;
}

export function useAgentNames(): UseAgentNamesReturn {
  const [names, setNames] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    let cancelled = false;

    async function fetchAgents() {
      try {
        const data = await apiClient<Agent[] | { agents: Agent[] }>("agents/");
        if (cancelled) return;

        const agents = Array.isArray(data) ? data : data.agents ?? [];
        const map = new Map<string, string>();
        for (const agent of agents) {
          map.set(agent.agent_id, agent.name);
        }
        setNames(map);
      } catch {
        // Fail silently — resolve() falls back to raw agent_id
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchAgents();

    return () => {
      cancelled = true;
    };
  }, []);

  const resolve = useCallback(
    (agentId: string): string => {
      return names.get(agentId) ?? agentId;
    },
    [names]
  );

  return { names, loading, resolve };
}
