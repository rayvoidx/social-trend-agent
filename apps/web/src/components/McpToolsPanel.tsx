import { useState } from 'react';
import api from '../api/client';
import { Search, Link, Lightbulb, Youtube, Loader2, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';

interface WebSearchResult {
  query: string;
  count: number;
  urls: string[];
}

interface FetchUrlResult {
  url: string;
  content?: string;
  error?: string;
}

interface InsightItem {
  id: string;
  source: string;
  query: string;
  time_window: string;
  language: string;
  top_keywords: string[];
  created_at: string;
}

interface InsightsResult {
  total: number;
  items: InsightItem[];
}

interface YouTubeVideo {
  video_id: string;
  title: string;
  channel_title: string;
  published_at: string;
  view_count?: number;
  like_count?: number;
  thumbnail_url?: string;
}

interface YouTubeSearchResult {
  query: string;
  count: number;
  videos: YouTubeVideo[];
}

type TabType = 'search' | 'fetch' | 'insights' | 'youtube';

export function McpToolsPanel() {
  const [activeTab, setActiveTab] = useState<TabType>('search');
  const [isExpanded, setIsExpanded] = useState(true);

  // Web Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<WebSearchResult | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);

  // Fetch URL State
  const [fetchUrl, setFetchUrl] = useState('');
  const [fetchResult, setFetchResult] = useState<FetchUrlResult | null>(null);
  const [fetchLoading, setFetchLoading] = useState(false);

  // Insights State
  const [insightsSource, setInsightsSource] = useState('');
  const [insightsResult, setInsightsResult] = useState<InsightsResult | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);

  // YouTube State
  const [youtubeQuery, setYoutubeQuery] = useState('');
  const [youtubeResults, setYoutubeResults] = useState<YouTubeSearchResult | null>(null);
  const [youtubeLoading, setYoutubeLoading] = useState(false);

  const handleWebSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      const result = await api.webSearch(searchQuery);
      setSearchResults(result);
    } catch (error) {
      console.error('Web search failed:', error);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleFetchUrl = async () => {
    if (!fetchUrl.trim()) return;
    setFetchLoading(true);
    try {
      const result = await api.fetchUrl(fetchUrl);
      setFetchResult(result);
    } catch (error) {
      console.error('Fetch URL failed:', error);
    } finally {
      setFetchLoading(false);
    }
  };

  const handleGetInsights = async () => {
    setInsightsLoading(true);
    try {
      const result = await api.getInsights(insightsSource || undefined);
      setInsightsResult(result);
    } catch (error) {
      console.error('Get insights failed:', error);
    } finally {
      setInsightsLoading(false);
    }
  };

  const handleYoutubeSearch = async () => {
    if (!youtubeQuery.trim()) return;
    setYoutubeLoading(true);
    try {
      const result = await api.youtubeSearch(youtubeQuery);
      setYoutubeResults(result);
    } catch (error) {
      console.error('YouTube search failed:', error);
    } finally {
      setYoutubeLoading(false);
    }
  };

  const tabs = [
    { id: 'search' as TabType, label: '웹 검색', icon: Search },
    { id: 'fetch' as TabType, label: 'URL 가져오기', icon: Link },
    { id: 'insights' as TabType, label: '인사이트', icon: Lightbulb },
    { id: 'youtube' as TabType, label: 'YouTube', icon: Youtube },
  ];

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <h3 className="font-semibold text-gray-900">MCP 도구</h3>
        {isExpanded ? (
          <ChevronUp className="h-5 w-5 text-gray-500" />
        ) : (
          <ChevronDown className="h-5 w-5 text-gray-500" />
        )}
      </div>

      {isExpanded && (
        <>
          {/* Tabs */}
          <div className="border-t border-b">
            <div className="flex">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-1 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <tab.icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Tab Content */}
          <div className="p-4">
            {/* Web Search Tab */}
            {activeTab === 'search' && (
              <div className="space-y-4">
                <div className="flex space-x-2">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="검색어 입력..."
                    className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    onKeyDown={(e) => e.key === 'Enter' && handleWebSearch()}
                  />
                  <button
                    onClick={handleWebSearch}
                    disabled={searchLoading || !searchQuery.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {searchLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Search className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {searchResults && (
                  <div className="space-y-2">
                    <p className="text-sm text-gray-600">
                      {searchResults.count}개 결과
                    </p>
                    <ul className="space-y-1 max-h-48 overflow-y-auto">
                      {searchResults.urls.map((url, idx) => (
                        <li key={idx} className="text-sm">
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline flex items-center space-x-1"
                          >
                            <span className="truncate">{url}</span>
                            <ExternalLink className="h-3 w-3 flex-shrink-0" />
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Fetch URL Tab */}
            {activeTab === 'fetch' && (
              <div className="space-y-4">
                <div className="flex space-x-2">
                  <input
                    type="url"
                    value={fetchUrl}
                    onChange={(e) => setFetchUrl(e.target.value)}
                    placeholder="URL 입력..."
                    className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    onKeyDown={(e) => e.key === 'Enter' && handleFetchUrl()}
                  />
                  <button
                    onClick={handleFetchUrl}
                    disabled={fetchLoading || !fetchUrl.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {fetchLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Link className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {fetchResult && (
                  <div className="space-y-2">
                    {fetchResult.error ? (
                      <p className="text-sm text-red-600">{fetchResult.error}</p>
                    ) : (
                      <div className="bg-gray-50 rounded p-3 max-h-48 overflow-y-auto">
                        <pre className="text-xs whitespace-pre-wrap">
                          {typeof fetchResult.content === 'string'
                            ? fetchResult.content.slice(0, 2000) + (fetchResult.content.length > 2000 ? '...' : '')
                            : JSON.stringify(fetchResult, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Insights Tab */}
            {activeTab === 'insights' && (
              <div className="space-y-4">
                <div className="flex space-x-2">
                  <select
                    value={insightsSource}
                    onChange={(e) => setInsightsSource(e.target.value)}
                    className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">모든 소스</option>
                    <option value="news_trend_agent">뉴스 트렌드</option>
                    <option value="viral_video_agent">바이럴 비디오</option>
                    <option value="social_trend_agent">소셜 트렌드</option>
                  </select>
                  <button
                    onClick={handleGetInsights}
                    disabled={insightsLoading}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {insightsLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Lightbulb className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {insightsResult && (
                  <div className="space-y-2">
                    <p className="text-sm text-gray-600">
                      {insightsResult.total}개 인사이트
                    </p>
                    <ul className="space-y-2 max-h-48 overflow-y-auto">
                      {insightsResult.items.map((item) => (
                        <li key={item.id} className="bg-gray-50 rounded p-2 text-sm">
                          <div className="font-medium text-gray-900">{item.query}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {item.source} | {item.time_window} | {new Date(item.created_at).toLocaleDateString()}
                          </div>
                          {item.top_keywords.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {item.top_keywords.map((kw, idx) => (
                                <span key={idx} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                                  {kw}
                                </span>
                              ))}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* YouTube Tab */}
            {activeTab === 'youtube' && (
              <div className="space-y-4">
                <div className="flex space-x-2">
                  <input
                    type="text"
                    value={youtubeQuery}
                    onChange={(e) => setYoutubeQuery(e.target.value)}
                    placeholder="YouTube 검색어..."
                    className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    onKeyDown={(e) => e.key === 'Enter' && handleYoutubeSearch()}
                  />
                  <button
                    onClick={handleYoutubeSearch}
                    disabled={youtubeLoading || !youtubeQuery.trim()}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {youtubeLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Youtube className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {youtubeResults && (
                  <div className="space-y-2">
                    <p className="text-sm text-gray-600">
                      {youtubeResults.count}개 동영상
                    </p>
                    <ul className="space-y-2 max-h-48 overflow-y-auto">
                      {youtubeResults.videos.map((video) => (
                        <li key={video.video_id} className="bg-gray-50 rounded p-2 text-sm">
                          <a
                            href={`https://youtube.com/watch?v=${video.video_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-gray-900 hover:text-blue-600"
                          >
                            {video.title}
                          </a>
                          <div className="text-xs text-gray-500 mt-1">
                            {video.channel_title} | {new Date(video.published_at).toLocaleDateString()}
                            {video.view_count && ` | ${video.view_count.toLocaleString()}회`}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
