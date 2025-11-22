import { useState } from 'react';
import { AnalysisForm } from './AnalysisForm';
import { ResultCard } from './ResultCard';
import type { AnalysisRequest, TaskStatus } from '../types';
import api from '../api/client';

export function Dashboard() {
  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (request: AnalysisRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const { task_id } = await api.submitTask(request);

      const newTask: TaskStatus = {
        task_id,
        agent_name: request.agent_type,
        query: request.query,
        status: 'pending',
        created_at: Date.now() / 1000,
      };

      setTasks(prev => [newTask, ...prev]);
      pollTaskStatus(task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setIsLoading(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const poll = async () => {
      try {
        const status = await api.getTaskStatus(taskId);
        setTasks(prev => prev.map(t => t.task_id === taskId ? status : t));

        if (status.status === 'pending' || status.status === 'running') {
          setTimeout(poll, 2000);
        }
      } catch (err) {
        console.error('Poll failed:', err);
      }
    };
    poll();
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <AnalysisForm onSubmit={handleSubmit} isLoading={isLoading} />

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-sm">
          {error}
        </div>
      )}

      {tasks.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium">Results</h2>
            <button
              onClick={() => setTasks([])}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Clear
            </button>
          </div>
          <div className="space-y-4">
            {tasks.map((task) => (
              <ResultCard key={task.task_id} task={task} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
