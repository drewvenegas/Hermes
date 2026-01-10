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

// Monochromatic type badges - varying intensities of sunset orange
const typeStyles: Record<string, string> = {
  agent_system: 'bg-sunset-500/20 text-sunset-400 border border-sunset-700/40',
  user_template: 'bg-sunset-600/15 text-sunset-500 border border-sunset-800/40',
  tool_definition: 'bg-sunset-700/15 text-sunset-600 border border-sunset-900/40',
  mcp_instruction: 'bg-sunset-800/20 text-sunset-500 border border-sunset-900/40',
};

// Monochromatic status badges
const statusStyles: Record<string, string> = {
  draft: 'bg-bravo-elevated text-bravo-muted border border-bravo-border-subtle',
  review: 'bg-sunset-700/15 text-sunset-600 border border-sunset-900/50',
  staged: 'bg-sunset-600/15 text-sunset-500 border border-sunset-800/50',
  deployed: 'bg-sunset-500/20 text-sunset-400 border border-sunset-700/50',
  archived: 'bg-sunset-950/30 text-sunset-700 border border-sunset-900/30',
};

export default function PromptList() {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter] = useState<string>('');

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
    <div className="p-8 animate-fade-in bg-bravo-bg min-h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-sunset-300 to-sunset-500 bg-clip-text text-transparent">
            Prompts
          </h1>
          <p className="text-bravo-muted mt-1">Manage your prompt library</p>
        </div>
        <Link
          to="/prompts/new"
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-sunset hover:opacity-90 rounded-lg transition-all shadow-sunset text-white font-medium"
        >
          <Plus className="w-5 h-5" />
          <span>New Prompt</span>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-bravo-muted" />
          <input
            type="text"
            placeholder="Search prompts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-bravo-surface border border-bravo-border rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none text-bravo-text placeholder-bravo-muted transition-colors"
          />
        </div>
        <div className="relative">
          <button className="flex items-center gap-2 px-4 py-2.5 bg-bravo-surface border border-bravo-border rounded-lg hover:border-sunset-700 text-bravo-text-secondary transition-colors">
            <Filter className="w-5 h-5" />
            <span>Type</span>
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="glass rounded-xl overflow-hidden border-glow">
        <table className="w-full">
          <thead>
            <tr className="border-b border-bravo-border">
              <th className="text-left px-6 py-4 text-xs font-semibold text-bravo-muted uppercase tracking-wider">Name</th>
              <th className="text-left px-6 py-4 text-xs font-semibold text-bravo-muted uppercase tracking-wider">Type</th>
              <th className="text-left px-6 py-4 text-xs font-semibold text-bravo-muted uppercase tracking-wider">Status</th>
              <th className="text-left px-6 py-4 text-xs font-semibold text-bravo-muted uppercase tracking-wider">Version</th>
              <th className="text-left px-6 py-4 text-xs font-semibold text-bravo-muted uppercase tracking-wider">Benchmark</th>
              <th className="text-left px-6 py-4 text-xs font-semibold text-bravo-muted uppercase tracking-wider">Updated</th>
              <th className="w-12"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-bravo-border-subtle">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-bravo-muted">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-5 h-5 border-2 border-bravo-border border-t-sunset-500 rounded-full animate-spin" />
                    Loading prompts...
                  </div>
                </td>
              </tr>
            ) : prompts.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-bravo-muted">
                  No prompts found. Create your first prompt to get started.
                </td>
              </tr>
            ) : (
              prompts.map((prompt) => (
                <tr key={prompt.id} className="hover:bg-bravo-elevated/50 transition-colors group">
                  <td className="px-6 py-4">
                    <Link to={`/prompts/${prompt.id}`} className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-bravo-elevated border border-bravo-border-subtle flex items-center justify-center group-hover:border-sunset-800 transition-colors">
                        <FileText className="w-4 h-4 text-bravo-muted group-hover:text-sunset-500 transition-colors" />
                      </div>
                      <div>
                        <p className="font-medium text-bravo-text group-hover:text-sunset-400 transition-colors">{prompt.name}</p>
                        <p className="text-xs text-bravo-muted font-mono">{prompt.slug}</p>
                      </div>
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 text-xs rounded-full font-medium ${typeStyles[prompt.type] || typeStyles.agent_system}`}>
                      {prompt.type.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 text-xs rounded-full font-medium ${statusStyles[prompt.status] || statusStyles.draft}`}>
                      {prompt.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-sm text-sunset-500">{prompt.version}</td>
                  <td className="px-6 py-4">
                    {prompt.benchmark_score ? (
                      <span className="font-semibold text-sunset-400">{prompt.benchmark_score.toFixed(1)}%</span>
                    ) : (
                      <span className="text-bravo-muted">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-bravo-muted">
                    {new Date(prompt.updated_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <button className="p-1.5 hover:bg-bravo-elevated rounded transition-colors">
                      <MoreVertical className="w-4 h-4 text-bravo-muted hover:text-sunset-500" />
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
