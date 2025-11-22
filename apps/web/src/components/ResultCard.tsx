import { CheckCircle, Clock, AlertCircle, Loader2 } from 'lucide-react';
import type { TaskStatus } from '../types';
import { MissionRecommendations } from './MissionRecommendations';

interface ResultCardProps {
  task: TaskStatus;
}

export function ResultCard({ task }: ResultCardProps) {
  const statusConfig = {
    pending: { icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-50', label: '대기 중' },
    running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-50', label: '분석 중' },
    completed: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-50', label: '완료' },
    failed: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-50', label: '실패' },
    cancelled: { icon: AlertCircle, color: 'text-gray-500', bg: 'bg-gray-50', label: '취소됨' },
  };

  const config = statusConfig[task.status] || statusConfig.failed;
  const StatusIcon = config.icon;

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <StatusIcon className={`h-5 w-5 ${config.color} ${task.status === 'running' ? 'animate-spin' : ''}`} />
          <span className={`text-sm font-medium px-2 py-1 rounded ${config.bg} ${config.color}`}>
            {config.label}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {task.task_id.slice(0, 8)}...
        </span>
      </div>

      <div className="space-y-3">
        <div>
          <span className="text-sm font-medium text-gray-700">쿼리: </span>
          <span className="text-sm text-gray-900">{task.query}</span>
        </div>

        <div>
          <span className="text-sm font-medium text-gray-700">에이전트: </span>
          <span className="text-sm text-gray-900">{task.agent_name}</span>
        </div>

        {task.duration && (
          <div>
            <span className="text-sm font-medium text-gray-700">실행 시간: </span>
            <span className="text-sm text-gray-900">{task.duration.toFixed(2)}초</span>
          </div>
        )}

        {task.result && (
          <>
            {task.result.sentiment && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-2">감성 분석</span>
                <div className="flex space-x-4">
                  <div className="text-center">
                    <div className="text-lg font-bold text-green-600">
                      {task.result.sentiment.positive_pct.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500">긍정</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-gray-600">
                      {task.result.sentiment.neutral_pct.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500">중립</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-red-600">
                      {task.result.sentiment.negative_pct.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500">부정</div>
                  </div>
                </div>
              </div>
            )}

            {task.result.keywords && task.result.keywords.length > 0 && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-2">주요 키워드</span>
                <div className="flex flex-wrap gap-2">
                  {task.result.keywords.slice(0, 5).map((kw, i) => (
                    <span
                      key={i}
                      className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full"
                    >
                      {kw.keyword} ({kw.count})
                    </span>
                  ))}
                </div>
              </div>
            )}

            {task.result.summary && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-1">요약</span>
                <p className="text-sm text-gray-600 line-clamp-3">{task.result.summary}</p>
              </div>
            )}

            {task.result.report_md && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-1">리포트</span>
                <p className="text-sm text-gray-600">{task.result.report_md}</p>
              </div>
            )}

            {task.result.insight_id && (
              <div>
                <span className="text-sm font-medium text-gray-700">인사이트 ID: </span>
                <span className="text-sm text-gray-500">{task.result.insight_id}</span>
              </div>
            )}

            {/* 추천 UI: 미션 & 크리에이터 */}
            <MissionRecommendations result={task.result} />
          </>
        )}
      </div>

      {task.error && (
        <div className="mt-2 p-2 bg-red-50 rounded text-sm text-red-600">
          {task.error}
        </div>
      )}
    </div>
  );
}
