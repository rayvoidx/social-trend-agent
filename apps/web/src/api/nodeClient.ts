import axios from 'axios'
import type { AnalysisResult, MissionRecommendationResponse } from '../types'

const NODE_API_BASE_URL = import.meta.env.VITE_NODE_API_URL || 'http://localhost:3001'

const nodeClient = axios.create({
  baseURL: NODE_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const nodeApi = {
  async recommendMissionsFromResult(
    result: AnalysisResult,
    options?: { target_audience?: string; budget?: number },
  ): Promise<MissionRecommendationResponse> {
    const body = {
      insight: {
        id: result.run_id,
        source: 'frontend',
        query: result.query,
        time_window: result.time_window,
        language: 'ko',
        sentiment_summary: result.sentiment
          ? `긍정 ${result.sentiment.positive_pct.toFixed(1)}% / 중립 ${result.sentiment.neutral_pct.toFixed(
              1,
            )}% / 부정 ${result.sentiment.negative_pct.toFixed(1)}%`
          : null,
        top_keywords: (result.keywords || []).map((k) => k.keyword),
        summary: result.summary,
        metrics: {
          // 간단한 휴리스틱: 키워드/감성 정보가 있으면 actionability 높게
          actionability: result.summary || result.keywords ? 0.9 : 0.5,
        },
        run_id: result.run_id,
        report_path: result.report_path,
      },
      target_audience: options?.target_audience,
      budget: options?.budget,
    }

    const response = await nodeClient.post('/missions/recommend', body)
    return response.data
  },
}

export default nodeApi


