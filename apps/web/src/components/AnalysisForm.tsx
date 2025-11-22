import { useState } from 'react';
import type { AnalysisRequest } from '../types';

interface AnalysisFormProps {
  onSubmit: (request: AnalysisRequest) => void;
  isLoading: boolean;
}

export function AnalysisForm({ onSubmit, isLoading }: AnalysisFormProps) {
  const [agentType, setAgentType] = useState<AnalysisRequest['agent_type']>('news_trend_agent');
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    onSubmit({
      agent_type: agentType,
      query: query.trim(),
      time_window: '7d',
      language: 'ko',
      params: { time_window: '7d', language: 'ko' }
    });
  };

  return (
    <div className="bg-white rounded-lg border p-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">Agent</label>
          <select
            value={agentType}
            onChange={(e) => setAgentType(e.target.value as AnalysisRequest['agent_type'])}
            className="w-full px-3 py-2 border rounded"
          >
            <option value="news_trend_agent">News</option>
            <option value="viral_video_agent">Video</option>
            <option value="social_trend_agent">Social</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Query</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter keywords..."
            className="w-full px-3 py-2 border rounded"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className={`w-full py-2 px-4 rounded font-medium text-white ${
            isLoading || !query.trim() ? 'bg-gray-400' : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {isLoading ? 'Analyzing...' : 'Analyze'}
        </button>
      </form>
    </div>
  );
}
