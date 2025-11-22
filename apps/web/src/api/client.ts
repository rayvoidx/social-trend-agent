import axios from 'axios';
import type { AnalysisRequest, TaskStatus } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // Health check
  async health() {
    const response = await apiClient.get('/api/health');
    return response.data;
  },

  // Submit analysis task
  async submitTask(request: AnalysisRequest): Promise<{ task_id: string }> {
    const response = await apiClient.post('/api/tasks', {
      agent_name: request.agent_type,
      query: request.query,
      params: request.params || {},
      priority: 1
    });
    return response.data;
  },

  // Get task status
  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const response = await apiClient.get(`/api/tasks/${taskId}`);
    return response.data;
  },

  // Get recent tasks
  async getRecentTasks(): Promise<TaskStatus[]> {
    const response = await apiClient.get('/api/tasks');
    return response.data.tasks || [];
  },

  // Get dashboard summary
  async getDashboardSummary() {
    const response = await apiClient.get('/api/dashboard/summary');
    return response.data;
  },

  // Get metrics
  async getMetrics() {
    const response = await apiClient.get('/api/metrics');
    return response.data;
  },

  // Get statistics
  async getStatistics() {
    const response = await apiClient.get('/api/statistics');
    return response.data;
  },

  // MCP Tools
  // Web search
  async webSearch(query: string, topK: number = 5) {
    const response = await apiClient.post('/api/mcp/web-search', { query, top_k: topK });
    return response.data;
  },

  // Fetch URL content
  async fetchUrl(url: string) {
    const response = await apiClient.post('/api/mcp/fetch-url', { url });
    return response.data;
  },

  // Get insights list
  async getInsights(source?: string, limit: number = 10) {
    const params = new URLSearchParams();
    if (source) params.append('source', source);
    params.append('limit', limit.toString());
    const response = await apiClient.get(`/api/mcp/insights?${params}`);
    return response.data;
  },

  // Recommend missions based on insight
  async recommendMissions(insightId: string) {
    const response = await apiClient.post('/api/mcp/recommend-missions', { insight_id: insightId });
    return response.data;
  },

  // YouTube search
  async youtubeSearch(query: string, maxResults: number = 10, channelId?: string) {
    const response = await apiClient.post('/api/mcp/youtube/search', {
      query,
      max_results: maxResults,
      channel_id: channelId
    });
    return response.data;
  },

  // YouTube channel videos
  async youtubeChannelVideos(channelId?: string, channelHandle?: string, maxResults: number = 10) {
    const response = await apiClient.post('/api/mcp/youtube/channel-videos', {
      channel_id: channelId,
      channel_handle: channelHandle,
      max_results: maxResults
    });
    return response.data;
  },

  // Get available MCP tools
  async getMcpTools() {
    const response = await apiClient.get('/api/mcp/tools');
    return response.data;
  },
};

export default api;
