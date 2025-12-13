import { useState } from 'react';
import { AnalysisForm } from './AnalysisForm';
import { ResultCard } from './ResultCard';
import { McpToolsPanel } from './McpToolsPanel';
import type { AnalysisRequest, TaskStatus } from '../types';
import api from '../api/client';
import { RefreshCw } from 'lucide-react';

export function Dashboard() {
  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (request: AnalysisRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      // Submit task
      const { task_id } = await api.submitTask(request);

      // Add to tasks list
      const newTask: TaskStatus = {
        task_id,
        agent_name: request.agent_type,
        query: request.query,
        status: 'pending',
        created_at: Date.now() / 1000,
      };

      setTasks(prev => [newTask, ...prev]);

      // Poll for status
      pollTaskStatus(task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : '분석 요청에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const maxAttempts = 60;
    let attempts = 0;

    const poll = async () => {
      try {
        const status = await api.getTaskStatus(taskId);

        setTasks(prev => prev.map(t =>
          t.task_id === taskId ? status : t
        ));

        if (status.status === 'pending' || status.status === 'running') {
          if (attempts < maxAttempts) {
            attempts++;
            setTimeout(poll, 2000);
          }
        }
      } catch (err) {
        console.error('Failed to poll task status:', err);
      }
    };

    poll();
  };

  const clearTasks = () => {
    setTasks([]);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Form & MCP Tools */}
        <div className="lg:col-span-1 space-y-4">
          <AnalysisForm onSubmit={handleSubmit} isLoading={isLoading} />

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          <McpToolsPanel />
        </div>

        {/* Right: Results */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">분석 결과</h2>
            {tasks.length > 0 && (
              <button
                onClick={clearTasks}
                className="flex items-center space-x-1 text-sm text-gray-500 hover:text-gray-700"
              >
                <RefreshCw className="h-4 w-4" />
                <span>초기화</span>
              </button>
            )}
          </div>

          {tasks.length === 0 ? (
            <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
              <p className="text-gray-500">분석 결과가 없습니다.</p>
              <p className="text-sm text-gray-400 mt-1">
                왼쪽 폼에서 분석을 시작해보세요.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {tasks.map((task) => (
                <ResultCard key={task.task_id} task={task} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
