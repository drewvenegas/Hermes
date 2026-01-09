import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Edit,
  Play,
  Copy,
  Trash2,
  GitBranch,
} from 'lucide-react';
import { api } from '../services/api';

interface Prompt {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  type: string;
  category: string | null;
  tags: string[] | null;
  content: string;
  version: string;
  status: string;
  benchmark_score: number | null;
  last_benchmark_at: string | null;
  created_at: string;
  updated_at: string;
}

interface Version {
  id: string;
  version: string;
  change_summary: string | null;
  created_at: string;
}

export default function PromptDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      loadPrompt(id);
      loadVersions(id);
    }
  }, [id]);

  const loadPrompt = async (promptId: string) => {
    try {
      const data = await api.getPrompt(promptId);
      setPrompt(data);
    } catch (error) {
      console.error('Failed to load prompt:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadVersions = async (promptId: string) => {
    try {
      const data = await api.getVersions(promptId);
      setVersions(data.items);
    } catch (error) {
      console.error('Failed to load versions:', error);
    }
  };

  const handleRunBenchmark = async () => {
    if (!id) return;
    try {
      await api.runBenchmark(id);
      loadPrompt(id);
    } catch (error) {
      console.error('Failed to run benchmark:', error);
    }
  };

  const handleDelete = async () => {
    if (!id || !confirm('Are you sure you want to delete this prompt?')) return;
    try {
      await api.deletePrompt(id);
      navigate('/prompts');
    } catch (error) {
      console.error('Failed to delete prompt:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-slate-400">Loading prompt...</p>
      </div>
    );
  }

  if (!prompt) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-slate-400">Prompt not found</p>
      </div>
    );
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div className="flex items-start gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-slate-800 rounded-lg transition-colors mt-1"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold">{prompt.name}</h1>
            <p className="text-slate-400 mt-1">{prompt.slug}</p>
            {prompt.description && (
              <p className="text-slate-300 mt-2 max-w-2xl">{prompt.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRunBenchmark}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <Play className="w-4 h-4" />
            <span>Benchmark</span>
          </button>
          <Link
            to={`/prompts/${id}/edit`}
            className="flex items-center gap-2 px-4 py-2 bg-sunset-500 hover:bg-sunset-600 rounded-lg transition-colors"
          >
            <Edit className="w-4 h-4" />
            <span>Edit</span>
          </Link>
          <button
            onClick={handleDelete}
            className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="glass rounded-xl p-4">
          <p className="text-sm text-slate-400">Type</p>
          <p className="font-medium mt-1">{prompt.type.replace('_', ' ')}</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-sm text-slate-400">Status</p>
          <p className="font-medium mt-1 capitalize">{prompt.status}</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-sm text-slate-400">Version</p>
          <p className="font-medium mt-1 font-mono">{prompt.version}</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-sm text-slate-400">Benchmark</p>
          <p className="font-medium mt-1">
            {prompt.benchmark_score ? `${prompt.benchmark_score.toFixed(1)}%` : '—'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Content */}
        <div className="lg:col-span-2">
          <div className="glass rounded-xl">
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
              <h2 className="font-semibold">Content</h2>
              <button
                onClick={() => navigator.clipboard.writeText(prompt.content)}
                className="flex items-center gap-1 text-sm text-slate-400 hover:text-white"
              >
                <Copy className="w-4 h-4" /> Copy
              </button>
            </div>
            <pre className="p-4 overflow-x-auto text-sm font-mono text-slate-300 whitespace-pre-wrap">
              {prompt.content}
            </pre>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Version History */}
          <div className="glass rounded-xl">
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
              <h2 className="font-semibold flex items-center gap-2">
                <GitBranch className="w-4 h-4" /> Version History
              </h2>
            </div>
            <div className="divide-y divide-slate-700">
              {versions.slice(0, 5).map((version) => (
                <div key={version.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm">{version.version}</span>
                    <span className="text-xs text-slate-400">
                      {new Date(version.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {version.change_summary && (
                    <p className="text-sm text-slate-400 mt-1">{version.change_summary}</p>
                  )}
                </div>
              ))}
              {versions.length === 0 && (
                <p className="p-4 text-sm text-slate-400">No version history</p>
              )}
            </div>
          </div>

          {/* Tags */}
          {prompt.tags && prompt.tags.length > 0 && (
            <div className="glass rounded-xl p-4">
              <h2 className="font-semibold mb-3">Tags</h2>
              <div className="flex flex-wrap gap-2">
                {prompt.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-1 text-xs bg-slate-700 rounded-full"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
