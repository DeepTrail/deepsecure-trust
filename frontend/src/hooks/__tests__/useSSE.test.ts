import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSSE } from "../useSSE";
import type { SSEStatus } from "../useSSE";

type EventSourceListener = ((event: MessageEvent | Event) => void) | null;

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  readyState = 0; // CONNECTING
  onopen: EventSourceListener = null;
  onmessage: EventSourceListener = null;
  onerror: EventSourceListener = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  simulateOpen() {
    this.readyState = 1; // OPEN
    this.onopen?.(new Event("open"));
  }

  simulateMessage(data: string) {
    this.onmessage?.(new MessageEvent("message", { data }));
  }

  simulateError() {
    this.readyState = 2; // CLOSED
    this.onerror?.(new Event("error"));
  }
}

describe("useSSE", () => {
  let originalEventSource: typeof EventSource;

  beforeEach(() => {
    vi.useFakeTimers();
    MockEventSource.instances = [];
    originalEventSource = globalThis.EventSource;
    globalThis.EventSource = MockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    vi.useRealTimers();
    globalThis.EventSource = originalEventSource;
  });

  function latestSource(): MockEventSource {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }

  it("connects to the given URL on mount", () => {
    renderHook(() => useSSE("/api/events/stream"));
    expect(MockEventSource.instances).toHaveLength(1);
    expect(latestSource().url).toBe("/api/events/stream");
  });

  it("reports 'connecting' status initially, then 'connected' on open", async () => {
    const { result } = renderHook(() => useSSE("/api/events/stream"));
    expect(result.current.status).toBe("connecting");
    expect(result.current.connected).toBe(false);

    act(() => latestSource().simulateOpen());

    expect(result.current.status).toBe("connected");
    expect(result.current.connected).toBe(true);
  });

  it("parses JSON messages into data array", () => {
    const { result } = renderHook(() =>
      useSSE<{ type: string }>("/api/events/stream")
    );

    act(() => {
      latestSource().simulateOpen();
      latestSource().simulateMessage('{"type":"audit"}');
      latestSource().simulateMessage('{"type":"policy"}');
    });

    expect(result.current.data).toEqual([
      { type: "audit" },
      { type: "policy" },
    ]);
    expect(result.current.lastEvent).toEqual({ type: "policy" });
  });

  it("ignores non-JSON messages without throwing", () => {
    const { result } = renderHook(() => useSSE("/api/events/stream"));
    act(() => {
      latestSource().simulateOpen();
      latestSource().simulateMessage("not json");
    });
    expect(result.current.data).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("clears data when clear() is called", () => {
    const { result } = renderHook(() =>
      useSSE<{ v: number }>("/api/events/stream")
    );
    act(() => {
      latestSource().simulateOpen();
      latestSource().simulateMessage('{"v":1}');
    });
    expect(result.current.data).toHaveLength(1);

    act(() => result.current.clear());
    expect(result.current.data).toEqual([]);
    expect(result.current.lastEvent).toBeNull();
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = renderHook(() => useSSE("/api/events/stream"));
    const source = latestSource();
    act(() => source.simulateOpen());
    unmount();
    expect(source.close).toHaveBeenCalled();
  });

  it("does not connect when enabled is false", () => {
    renderHook(() => useSSE("/api/events/stream", { enabled: false }));
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("reconnects with backoff on error", () => {
    renderHook(() =>
      useSSE("/api/events/stream", { baseDelayMs: 100, maxRetries: 3 })
    );
    expect(MockEventSource.instances).toHaveLength(1);

    act(() => latestSource().simulateError());
    expect(MockEventSource.instances).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(MockEventSource.instances).toHaveLength(2);
  });

  it("sets error status after max retries exhausted", () => {
    const { result } = renderHook(() =>
      useSSE("/api/events/stream", {
        maxRetries: 2,
        baseDelayMs: 50,
      })
    );

    act(() => latestSource().simulateError());
    act(() => vi.advanceTimersByTime(200));
    act(() => latestSource().simulateError());
    act(() => vi.advanceTimersByTime(400));
    act(() => latestSource().simulateError());

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error!.message).toContain("2 retries");
  });

  it("resets retry count after successful reconnection", () => {
    const { result } = renderHook(() =>
      useSSE("/api/events/stream", { baseDelayMs: 50, maxRetries: 5 })
    );

    act(() => latestSource().simulateError());
    act(() => vi.advanceTimersByTime(200));
    act(() => latestSource().simulateOpen());

    expect(result.current.status).toBe("connected");

    act(() => latestSource().simulateError());
    act(() => vi.advanceTimersByTime(200));
    act(() => latestSource().simulateOpen());

    expect(result.current.status).toBe("connected");
    expect(result.current.error).toBeNull();
  });

  it("reconnects when URL changes", () => {
    const { rerender } = renderHook(
      ({ url }: { url: string }) => useSSE(url),
      { initialProps: { url: "/api/events/a" } }
    );

    const firstSource = latestSource();
    act(() => firstSource.simulateOpen());

    rerender({ url: "/api/events/b" });

    expect(firstSource.close).toHaveBeenCalled();
    expect(MockEventSource.instances).toHaveLength(2);
    expect(latestSource().url).toBe("/api/events/b");
  });

  it("transitions through correct status lifecycle", () => {
    const statuses: SSEStatus[] = [];
    const { result } = renderHook(() => {
      const sse = useSSE("/api/events/stream");
      statuses.push(sse.status);
      return sse;
    });

    act(() => latestSource().simulateOpen());
    act(() => latestSource().simulateError());

    expect(statuses).toContain("connecting");
    expect(statuses).toContain("connected");
    expect(statuses).toContain("disconnected");
  });
});
