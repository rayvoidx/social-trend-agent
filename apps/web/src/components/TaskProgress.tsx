import type { TaskStreamState } from "../types";

interface TaskProgressProps {
  streamState: TaskStreamState;
}

const NODE_ICONS: Record<string, string> = {
  router: "🔀",
  collect: "📥",
  plan: "📋",
  normalize: "🔧",
  analyze: "📊",
  rag: "🔍",
  summarize: "💡",
  critic: "🔎",
  report: "📝",
  notify: "🔔",
};

export function TaskProgress({ streamState }: TaskProgressProps) {
  const { progress, currentNode, currentLabel, completedNodes, error } =
    streamState;

  if (error) {
    return (
      <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-sm text-red-600">스트리밍 오류: {error}</p>
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-3">
      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-600">
            진행률 {progress}%
          </span>
          {currentLabel && (
            <span className="text-xs text-blue-600 flex items-center gap-1">
              <span className="inline-block w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
              {currentLabel}
            </span>
          )}
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Completed nodes */}
      {completedNodes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {completedNodes.map((node) => (
            <span
              key={node}
              className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 border border-green-200 text-green-700 text-xs rounded-full"
            >
              <span>{NODE_ICONS[node] || "✅"}</span>
              {node}
            </span>
          ))}
          {currentNode && !completedNodes.includes(currentNode) && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-700 text-xs rounded-full animate-pulse">
              <span>{NODE_ICONS[currentNode] || "⏳"}</span>
              {currentNode}
            </span>
          )}
        </div>
      )}

      {/* Preview data from last node */}
      {streamState.events.length > 0 &&
        (() => {
          const lastNodeEvent = [...streamState.events]
            .reverse()
            .find((e) => e.event === "node_complete" && e.data.preview);
          if (!lastNodeEvent?.data.preview) return null;
          const preview = lastNodeEvent.data.preview;
          const entries = Object.entries(preview).filter(
            ([, v]) => v !== undefined && v !== null,
          );
          if (entries.length === 0) return null;

          return (
            <div className="text-xs text-gray-500 bg-gray-50 rounded p-2 space-y-0.5">
              {entries.map(([key, value]) => (
                <div key={key}>
                  <span className="font-medium">{key}: </span>
                  <span>
                    {typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value)}
                  </span>
                </div>
              ))}
            </div>
          );
        })()}
    </div>
  );
}
