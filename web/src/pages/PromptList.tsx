import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus,
  Search,
  Filter,
  FileText,
  MoreVertical,
  ChevronDown,
} from 'lucide-react';
import { api } from '../services/api';

interface Prompt {
  id: string;
  slug: string;
  name: string;
  type: string;
  category: string | null;
  status: string;
  version: string;
  benchmark_score: number | null;
  updated_at: string;
}

const typeColors: Record<string, string> = {
  agent_system: 'bg-purple-500/20 text-purple-400',
  user_template: 'bg-blue-500/20 text-blue-400',
  tool_definition: 'bg-green-500/20 text-green-400',
  mcp_instruction: 'bg-orange-500/20 text-orange-400',
};

const statusColors: Record<string, string> = {
  draft: 'bg-slate-500/20 text-slate-400',
  review: 'bg-yellow-500/20 text-yellow-400',
  staged: 'bg-blue-500/20 text-blue-400',
  deployed: 'bg-green-500/20 text-green-400',
  archived: 'bg-red-500/20 text-red-400',
};

export default function PromptList() {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  useEffect(() => {
    loadPrompts();
  }, [search, typeFilter]);

  const loadPrompts = async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (typeFilter) params.type = typeFilter;
      const data = await api.getPrompts(params);
      setPrompts(data.items);
    } catch (error) {
      console.error('Failed to load prompts:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Prompts</h1>
          <p className="text-slate-400 mt-1">Manage your prompt library</p>
        </div>
        <Link
          to="/prompts/new"
          className="flex items-center gap-2 px-4 py-2 bg-sunset-500 hover:bg-sunset-600 rounded-lg transition-colors"
        >
          <Plus className="w-5 h-5" />
          <span>New Prompt</span>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            placeholder="Search prompts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none"
          />
        </div>
        <div className="relative">
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg hover:border-slate-600">
            <Filter className="w-5 h-5" />
            <span>Type</span>
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="glass rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Name</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Type</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Status</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Version</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Benchmark</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Updated</th>
              <th className="w-12"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                  Loading prompts...
                </td>
              </tr>
            ) : prompts.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                  No prompts found. Create your first prompt to get started.
                </td>
              </tr>
            ) : (
              prompts.map((prompt) => (
                <tr key={prompt.id} className="hover:bg-slate-800/50 transition-colors">
                  <td className="px-6 py-4">
                    <Link to={`/prompts/${prompt.id}`} className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center">
                        <FileText className="w-4 h-4 text-slate-400" />
                      </div>
                      <div>
                        <p className="font-medium hover:text-sunset-400">{prompt.name}</p>
                        <p className="text-xs text-slate-500">{prompt.slug}</p>
                      </div>
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs rounded-full ${typeColors[prompt.type] || 'bg-slate-500/20 text-slate-400'}`}>
                      {prompt.type.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs rounded-full ${statusColors[prompt.status] || 'bg-slate-500/20 text-slate-400'}`}>
                      {prompt.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-sm">{prompt.version}</td>
                  <td className="px-6 py-4">
                    {prompt.benchmark_score ? (
                      <span className="font-medium">{prompt.benchmark_score.toFixed(1)}%</span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-400">
                    {new Date(prompt.updated_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <button className="p-1 hover:bg-slate-700 rounded">
                      <MoreVertical className="w-4 h-4 text-slate-400" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
