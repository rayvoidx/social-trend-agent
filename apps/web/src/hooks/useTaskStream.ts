import { useState, useCallback, useRef } from "react";
import type { StreamEventData, TaskStreamState } from "../types";
import api from "../api/client";

const initialState: TaskStreamState = {
  events: [],
  currentNode: null,
  currentLabel: null,
  progress: 0,
  isStreaming: false,
  completedNodes: [],
  error: null,
};

export function useTaskStream() {
  const [streams, setStreams] = useState<Record<string, TaskStreamState>>({});
  const eventSourcesRef = useRef<Record<string, EventSource>>({});

  const startStream = useCallback((taskId: string) => {
    // Initialize state
    setStreams((prev) => ({
      ...prev,
      [taskId]: { ...initialState, isStreaming: true },
    }));

    const eventSource = api.createTaskStream(
      taskId,
      (event: StreamEventData) => {
        setStreams((prev) => {
          const current = prev[taskId] || { ...initialState };
          const newEvents = [...current.events, event];

          if (event.event === "node_complete") {
            return {
              ...prev,
              [taskId]: {
                ...current,
                events: newEvents,
                currentNode: event.data.node || null,
                currentLabel: event.data.label || null,
                progress: event.data.progress || current.progress,
                completedNodes: event.data.node
                  ? [...current.completedNodes, event.data.node]
                  : current.completedNodes,
                isStreaming: true,
              },
            };
          }

          if (event.event === "complete") {
            return {
              ...prev,
              [taskId]: {
                ...current,
                events: newEvents,
                progress: 100,
                isStreaming: false,
                currentNode: null,
                currentLabel: null,
              },
            };
          }

          if (event.event === "error") {
            return {
              ...prev,
              [taskId]: {
                ...current,
                events: newEvents,
                isStreaming: false,
                error: event.data.error || "Unknown error",
              },
            };
          }

          if (event.event === "started") {
            return {
              ...prev,
              [taskId]: {
                ...current,
                events: newEvents,
                isStreaming: true,
                progress: 0,
              },
            };
          }

          return { ...prev, [taskId]: { ...current, events: newEvents } };
        });

        // Close EventSource on terminal events
        if (event.event === "complete" || event.event === "error") {
          const es = eventSourcesRef.current[taskId];
          if (es) {
            es.close();
            delete eventSourcesRef.current[taskId];
          }
        }
      },
      () => {
        // On SSE error, mark as not streaming (fallback to polling)
        setStreams((prev) => ({
          ...prev,
          [taskId]: {
            ...(prev[taskId] || initialState),
            isStreaming: false,
          },
        }));
      },
    );

    eventSourcesRef.current[taskId] = eventSource;
  }, []);

  const getStreamState = useCallback(
    (taskId: string): TaskStreamState | undefined => {
      return streams[taskId];
    },
    [streams],
  );

  return { streams, startStream, getStreamState };
}
