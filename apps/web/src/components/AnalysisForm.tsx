import { useState } from 'react';
import { Search, Newspaper, Video, MessageCircle } from 'lucide-react';
import type { AnalysisRequest } from '../types';

interface AnalysisFormProps {
  onSubmit: (request: AnalysisRequest) => void;
  isLoading: boolean;
}

export function AnalysisForm({ onSubmit, isLoading }: AnalysisFormProps) {
  const [agentType, setAgentType] = useState<AnalysisRequest['agent_type']>('news_trend_agent');
  const [query, setQuery] = useState('');
  const [timeWindow, setTimeWindow] = useState('7d');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    onSubmit({
      agent_type: agentType,
      query: query.trim(),
      time_window: timeWindow,
      language: 'ko',
      params: {
        time_window: timeWindow,
        language: 'ko',
      }
    });
  };

  const agents = [
    { id: 'news_trend_agent' as const, name: '뉴스 트렌드', icon: Newspaper, desc: '언론 보도 분석' },
    { id: 'viral_video_agent' as const, name: '바이럴 비디오', icon: Video, desc: 'YouTube/TikTok' },
    { id: 'social_trend_agent' as const, name: '소셜 트렌드', icon: MessageCircle, desc: 'X/Instagram' },
  ];

  return (
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">새 분석 시작</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Agent Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            에이전트 선택
          </label>
          <div className="grid grid-cols-3 gap-3">
            {agents.map((agent) => (
              <button
                key={agent.id}
                type="button"
                onClick={() => setAgentType(agent.id)}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  agentType === agent.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <agent.icon className={`h-5 w-5 mb-1 ${
                  agentType === agent.id ? 'text-blue-600' : 'text-gray-400'
                }`} />
                <div className="font-medium text-sm">{agent.name}</div>
                <div className="text-xs text-gray-500">{agent.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Query Input */}
        <div>
          <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-2">
            검색 키워드
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              id="query"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="AI 마케팅, 브랜드명, 해시태그..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Time Window */}
        <div>
          <label htmlFor="timeWindow" className="block text-sm font-medium text-gray-700 mb-2">
            분석 기간
          </label>
          <select
            id="timeWindow"
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="24h">최근 24시간</option>
            <option value="7d">최근 7일</option>
            <option value="30d">최근 30일</option>
          </select>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-colors ${
            isLoading || !query.trim()
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {isLoading ? '분석 중...' : '분석 시작'}
        </button>
      </form>
    </div>
  );
}
