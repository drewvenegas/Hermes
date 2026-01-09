/**
 * Hermes API Client
 */

import axios, { AxiosInstance } from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '';

const client: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('hermes_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export interface PromptListResponse {
  items: Prompt[];
  total: number;
  limit: number;
  offset: number;
}

export interface Prompt {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  type: string;
  category: string | null;
  tags: string[] | null;
  content: string;
  variables: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  version: string;
  content_hash: string;
  status: string;
  owner_id: string;
  owner_type: string;
  team_id: string | null;
  visibility: string;
  app_scope: string[] | null;
  repo_scope: string[] | null;
  benchmark_score: number | null;
  last_benchmark_at: string | null;
  deployed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VersionListResponse {
  items: Version[];
  total: number;
  limit: number;
  offset: number;
}

export interface Version {
  id: string;
  prompt_id: string;
  version: string;
  content: string;
  content_hash: string;
  diff: string | null;
  change_summary: string | null;
  author_id: string;
  variables: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  benchmark_results: Record<string, unknown> | null;
  created_at: string;
}

export interface BenchmarkResult {
  id: string;
  prompt_id: string;
  prompt_version: string;
  suite_id: string;
  overall_score: number;
  dimension_scores: Record<string, number>;
  model_id: string;
  model_version: string | null;
  execution_time_ms: number;
  token_usage: Record<string, unknown> | null;
  baseline_score: number | null;
  delta: number | null;
  gate_passed: boolean;
  executed_at: string;
  executed_by: string;
  environment: string;
}

export const api = {
  // Prompts
  async getPrompts(params?: Record<string, string>): Promise<PromptListResponse> {
    const { data } = await client.get('/prompts', { params });
    return data;
  },

  async getPrompt(id: string): Promise<Prompt> {
    const { data } = await client.get(`/prompts/${id}`);
    return data;
  },

  async getPromptBySlug(slug: string): Promise<Prompt> {
    const { data } = await client.get(`/prompts/by-slug/${slug}`);
    return data;
  },

  async createPrompt(prompt: Partial<Prompt>): Promise<Prompt> {
    const { data } = await client.post('/prompts', prompt);
    return data;
  },

  async updatePrompt(id: string, prompt: Partial<Prompt>): Promise<Prompt> {
    const { data } = await client.put(`/prompts/${id}`, prompt);
    return data;
  },

  async deletePrompt(id: string): Promise<void> {
    await client.delete(`/prompts/${id}`);
  },

  // Versions
  async getVersions(promptId: string): Promise<VersionListResponse> {
    const { data } = await client.get(`/prompts/${promptId}/versions`);
    return data;
  },

  async getVersion(promptId: string, version: string): Promise<Version> {
    const { data } = await client.get(`/prompts/${promptId}/versions/${version}`);
    return data;
  },

  async getDiff(promptId: string, fromVersion: string, toVersion: string): Promise<{ diff: string }> {
    const { data } = await client.get(`/prompts/${promptId}/diff`, {
      params: { from_version: fromVersion, to_version: toVersion },
    });
    return data;
  },

  async rollback(promptId: string, version: string): Promise<Prompt> {
    const { data } = await client.post(`/prompts/${promptId}/rollback`, { version });
    return data;
  },

  // Benchmarks
  async runBenchmark(promptId: string, suiteId = 'default'): Promise<BenchmarkResult> {
    const { data } = await client.post(`/prompts/${promptId}/benchmark`, {
      suite_id: suiteId,
      model_id: 'aria01-d3n',
    });
    return data;
  },

  async getBenchmarks(promptId: string): Promise<{ items: BenchmarkResult[] }> {
    const { data } = await client.get(`/prompts/${promptId}/benchmarks`);
    return data;
  },
};

export default api;
