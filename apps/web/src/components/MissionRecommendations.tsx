import { useState } from 'react'
import type { AnalysisResult, MissionRecommendationResponse } from '../types'
import nodeApi from '../api/nodeClient'

interface MissionRecommendationsProps {
  result: AnalysisResult
}

export function MissionRecommendations({ result }: MissionRecommendationsProps) {
  const [data, setData] = useState<MissionRecommendationResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRecommend = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await nodeApi.recommendMissionsFromResult(result, {
        target_audience: '일반 소비자',
        budget: 1_000_000,
      })
      setData(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : '미션 추천에 실패했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="mt-4 border-t pt-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-900">미션 & 크리에이터 추천</h3>
        <button
          type="button"
          onClick={handleRecommend}
          disabled={isLoading}
          className="text-xs px-3 py-1 rounded-full border border-blue-500 text-blue-600 hover:bg-blue-50 disabled:opacity-50"
        >
          {isLoading ? '추천 생성 중...' : '추천 생성'}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-600 mb-2">
          {error}
        </p>
      )}

      {!data && !error && (
        <p className="text-xs text-gray-500">
          이 분석 결과를 기반으로 실행 가능한 미션과 적합한 크리에이터를 추천받을 수 있습니다.
        </p>
      )}

      {data && data.recommendations.length === 0 && (
        <p className="text-xs text-gray-500">
          추천할 미션이 없습니다. 쿼리나 기간을 변경해 다시 시도해보세요.
        </p>
      )}

      {data && data.recommendations.length > 0 && (
        <div className="space-y-3 mt-2">
          {data.recommendations.map((rec) => (
            <div
              key={rec.mission.id}
              className="border rounded-lg p-3 bg-slate-50"
            >
              <div className="mb-1">
                <p className="text-xs text-slate-500 mb-1">미션</p>
                <p className="text-sm font-semibold text-slate-900">{rec.mission.title}</p>
                <p className="text-xs text-slate-600 mt-1 line-clamp-2">
                  {rec.mission.description}
                </p>
                <p className="mt-1 text-[11px] text-slate-500">
                  플랫폼: {rec.mission.platforms.join(', ') || 'N/A'}
                  {rec.mission.budget != null && ` · 예산: ${rec.mission.budget.toLocaleString()}원`}
                </p>
              </div>

              {rec.creators.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-slate-500 mb-1">추천 크리에이터</p>
                  <div className="space-y-1">
                    {rec.creators.slice(0, 3).map((c) => (
                      <div
                        key={c.id}
                        className="flex items-center justify-between text-xs bg-white rounded-md px-2 py-1 border"
                      >
                        <div>
                          <p className="font-medium text-slate-900">{c.name}</p>
                          <p className="text-[11px] text-slate-500">
                            {c.primary_platform}
                          </p>
                        </div>
                        <div className="text-right text-[11px] text-slate-500">
                          {c.followers != null && (
                            <p>팔로워 {c.followers.toLocaleString()}</p>
                          )}
                          {c.avg_view_per_post != null && (
                            <p>평균 조회수 {c.avg_view_per_post.toLocaleString()}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


