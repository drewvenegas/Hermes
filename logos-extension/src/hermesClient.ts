/**
 * Hermes API Client
 * 
 * Provides communication with the Hermes server via REST and gRPC.
 */

import axios, { AxiosInstance } from 'axios';
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';

export interface Prompt {
    id: string;
    slug: string;
    name: string;
    description?: string;
    type: string;
    category?: string;
    content: string;
    version: string;
    status: string;
    benchmark_score?: number;
    metadata?: Record<string, any>;
    variables?: Record<string, string>;
}

export interface BenchmarkResult {
    id: string;
    prompt_id: string;
    prompt_version: string;
    suite_id: string;
    overall_score: number;
    dimension_scores: Record<string, number>;
    model_id: string;
    execution_time_ms: number;
    gate_passed: boolean;
    delta?: number;
}

export interface SelfCritiqueResult {
    overall_assessment: string;
    quality_score: number;
    suggestions: Array<{
        id: string;
        category: string;
        severity: string;
        description: string;
        suggested_change?: string;
        confidence: number;
    }>;
    knowledge_gaps: string[];
    overconfidence_areas: string[];
}

export interface VersionInfo {
    id: string;
    prompt_id: string;
    version: string;
    content_hash: string;
    change_summary?: string;
    created_at: string;
}

export interface QualityGateResult {
    can_deploy: boolean;
    gate_report: {
        overall_status: string;
        summary: string;
        evaluations: Array<{
            gate_id: string;
            gate_name: string;
            status: string;
            message: string;
            blocking: boolean;
        }>;
    };
    blockers: string[];
    warnings: string[];
}

export class HermesClient {
    private http: AxiosInstance;
    private grpcClient: any;
    private grpcUrl: string;
    private token?: string;
    
    constructor(serverUrl: string, grpcUrl: string) {
        this.grpcUrl = grpcUrl;
        
        this.http = axios.create({
            baseURL: serverUrl,
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        // Add auth interceptor
        this.http.interceptors.request.use((config) => {
            if (this.token) {
                config.headers.Authorization = `Bearer ${this.token}`;
            }
            return config;
        });
    }
    
    setToken(token: string) {
        this.token = token;
    }
    
    close() {
        if (this.grpcClient) {
            grpc.closeClient(this.grpcClient);
        }
    }
    
    // =========================================================================
    // Prompt Operations
    // =========================================================================
    
    async listPrompts(params?: {
        type?: string;
        status?: string;
        category?: string;
        limit?: number;
        offset?: number;
    }): Promise<{ items: Prompt[]; total: number }> {
        const response = await this.http.get('/api/v1/prompts', { params });
        return response.data;
    }
    
    async getPrompt(id: string, version?: string): Promise<Prompt | null> {
        try {
            const params = version ? { version } : {};
            const response = await this.http.get(`/api/v1/prompts/${id}`, { params });
            return response.data;
        } catch (error: any) {
            if (error.response?.status === 404) {
                return null;
            }
            throw error;
        }
    }
    
    async getPromptBySlug(slug: string): Promise<Prompt | null> {
        try {
            const response = await this.http.get(`/api/v1/prompts/by-slug/${slug}`);
            return response.data;
        } catch (error: any) {
            if (error.response?.status === 404) {
                return null;
            }
            throw error;
        }
    }
    
    async createPrompt(data: {
        name: string;
        slug?: string;
        content: string;
        type?: string;
        description?: string;
        category?: string;
    }): Promise<Prompt> {
        const response = await this.http.post('/api/v1/prompts', data);
        return response.data;
    }
    
    async updatePrompt(
        id: string,
        content: string,
        changeSummary?: string
    ): Promise<Prompt> {
        const response = await this.http.put(`/api/v1/prompts/${id}`, {
            content,
            change_summary: changeSummary,
        });
        return response.data;
    }
    
    async deletePrompt(id: string): Promise<void> {
        await this.http.delete(`/api/v1/prompts/${id}`);
    }
    
    // =========================================================================
    // Version Operations
    // =========================================================================
    
    async getVersionHistory(promptId: string, limit = 20): Promise<VersionInfo[]> {
        const response = await this.http.get(
            `/api/v1/prompts/${promptId}/versions`,
            { params: { limit } }
        );
        return response.data.items || response.data;
    }
    
    async diffVersions(
        promptId: string,
        fromVersion: string,
        toVersion: string
    ): Promise<{ diff: string; chunks: any[] }> {
        const response = await this.http.get(
            `/api/v1/prompts/${promptId}/versions/${fromVersion}/diff/${toVersion}`
        );
        return response.data;
    }
    
    async rollbackVersion(promptId: string, toVersion: string): Promise<Prompt> {
        const response = await this.http.post(
            `/api/v1/prompts/${promptId}/rollback`,
            { to_version: toVersion }
        );
        return response.data;
    }
    
    // =========================================================================
    // Benchmark Operations
    // =========================================================================
    
    async runBenchmark(
        promptId: string,
        suiteId = 'default',
        modelId = 'aria01-d3n'
    ): Promise<BenchmarkResult> {
        const response = await this.http.post(
            `/api/v1/prompts/${promptId}/benchmark`,
            {
                suite_id: suiteId,
                model_id: modelId,
            }
        );
        return response.data;
    }
    
    async getBenchmarkHistory(promptId: string, limit = 10): Promise<BenchmarkResult[]> {
        const response = await this.http.get(
            `/api/v1/prompts/${promptId}/benchmarks`,
            { params: { limit } }
        );
        return response.data.items || response.data;
    }
    
    async runSelfCritique(promptId: string): Promise<SelfCritiqueResult> {
        const response = await this.http.post(
            `/api/v1/prompts/${promptId}/critique`
        );
        return response.data;
    }
    
    // =========================================================================
    // Quality Gate Operations
    // =========================================================================
    
    async checkQualityGate(
        promptId: string,
        environment = 'production'
    ): Promise<QualityGateResult> {
        const response = await this.http.get(
            `/api/v1/quality-gates/readiness/${promptId}`,
            { params: { environment } }
        );
        return response.data;
    }
    
    // =========================================================================
    // Search
    // =========================================================================
    
    async searchPrompts(query: string, limit = 20): Promise<{
        results: Array<{ prompt: Prompt; score: number }>;
        total: number;
    }> {
        const response = await this.http.get('/api/v1/search/prompts', {
            params: { q: query, limit },
        });
        return response.data;
    }
    
    // =========================================================================
    // Suites
    // =========================================================================
    
    async getBenchmarkSuites(): Promise<Array<{
        id: string;
        name: string;
        description: string;
        dimensions: string[];
    }>> {
        const response = await this.http.get('/api/v1/benchmark-suites');
        return response.data;
    }
}
