"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type SSEStatus = "connecting" | "connected" | "disconnected" | "error";

export interface UseSSEOptions {
  enabled?: boolean;
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
}

export interface UseSSEReturn<T> {
  data: T[];
  lastEvent: T | null;
  error: Error | null;
  status: SSEStatus;
  connected: boolean;
  clear: () => void;
}

const DEFAULT_OPTIONS: Required<UseSSEOptions> = {
  enabled: true,
  maxRetries: 10,
  baseDelayMs: 1000,
  maxDelayMs: 30_000,
};

function backoffDelay(
  attempt: number,
  baseMs: number,
  maxMs: number
): number {
  const exponential = baseMs * Math.pow(2, attempt);
  const jitter = Math.random() * baseMs;
  return Math.min(exponential + jitter, maxMs);
}

export function useSSE<T = unknown>(
  url: string,
  options?: UseSSEOptions
): UseSSEReturn<T> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const [data, setData] = useState<T[]>([]);
  const [lastEvent, setLastEvent] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [status, setStatus] = useState<SSEStatus>("disconnected");

  const retriesRef = useRef(0);
  const sourceRef = useRef<EventSource | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const clear = useCallback(() => {
    setData([]);
    setLastEvent(null);
    setError(null);
    setStatus((prev) => (prev === "error" ? "disconnected" : prev));
  }, []);

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    if (!opts.enabled) {
      cleanup();
      setStatus("disconnected");
      return;
    }

    function connect() {
      if (!mountedRef.current) return;
      cleanup();

      setStatus("connecting");
      const source = new EventSource(url);
      sourceRef.current = source;

      source.onopen = () => {
        if (!mountedRef.current) return;
        retriesRef.current = 0;
        setError(null);
        setStatus("connected");
      };

      source.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const parsed = JSON.parse(event.data) as T;
          setData((prev) => [...prev, parsed]);
          setLastEvent(parsed);
        } catch {
          // non-JSON events are silently skipped
        }
      };

      source.onerror = () => {
        if (!mountedRef.current) return;
        source.close();
        sourceRef.current = null;

        if (retriesRef.current >= opts.maxRetries) {
          setStatus("error");
          setError(new Error(`SSE connection failed after ${opts.maxRetries} retries`));
          return;
        }

        setStatus("disconnected");
        const delay = backoffDelay(
          retriesRef.current,
          opts.baseDelayMs,
          opts.maxDelayMs
        );
        retriesRef.current += 1;
        timerRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, opts.enabled]);

  return { data, lastEvent, error, status, connected: status === "connected", clear };
}
