import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Edit,
  Play,
  Copy,
  Trash2,
  GitBranch,
  Check,
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
  const [copied, setCopied] = useState(false);

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

  const handleCopy = () => {
    if (!prompt) return;
    navigator.clipboard.writeText(prompt.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-bravo-bg">
        <div className="flex items-center gap-2 text-bravo-muted">
          <div className="w-5 h-5 border-2 border-bravo-border border-t-sunset-500 rounded-full animate-spin" />
          Loading prompt...
        </div>
      </div>
    );
  }

  if (!prompt) {
    return (
      <div className="flex items-center justify-center h-full bg-bravo-bg">
        <p className="text-bravo-muted">Prompt not found</p>
      </div>
    );
  }

  return (
    <div className="p-8 animate-fade-in bg-bravo-bg min-h-full">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div className="flex items-start gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-bravo-elevated rounded-lg transition-colors mt-1 text-bravo-muted hover:text-bravo-text"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-sunset-300 to-sunset-500 bg-clip-text text-transparent">
              {prompt.name}
            </h1>
            <p className="text-bravo-muted mt-1 font-mono">{prompt.slug}</p>
            {prompt.description && (
              <p className="text-bravo-text-secondary mt-2 max-w-2xl">{prompt.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRunBenchmark}
            className="flex items-center gap-2 px-4 py-2.5 bg-bravo-surface border border-bravo-border hover:border-sunset-700 rounded-lg transition-colors text-bravo-text"
          >
            <Play className="w-4 h-4" />
            <span>Benchmark</span>
          </button>
          <Link
            to={`/prompts/${id}/edit`}
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-sunset hover:opacity-90 rounded-lg transition-all shadow-sunset text-white font-medium"
          >
            <Edit className="w-4 h-4" />
            <span>Edit</span>
          </Link>
          <button
            onClick={handleDelete}
            className="p-2.5 text-sunset-700 hover:bg-sunset-700/15 rounded-lg transition-colors"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="glass rounded-xl p-4 border-glow">
          <p className="text-xs font-semibold text-bravo-muted uppercase tracking-wider">Type</p>
          <p className="font-medium mt-1 text-bravo-text">{prompt.type.replace('_', ' ')}</p>
        </div>
        <div className="glass rounded-xl p-4 border-glow">
          <p className="text-xs font-semibold text-bravo-muted uppercase tracking-wider">Status</p>
          <p className="font-medium mt-1 text-bravo-text capitalize">{prompt.status}</p>
        </div>
        <div className="glass rounded-xl p-4 border-glow">
          <p className="text-xs font-semibold text-bravo-muted uppercase tracking-wider">Version</p>
          <p className="font-medium mt-1 font-mono text-sunset-500">{prompt.version}</p>
        </div>
        <div className="glass rounded-xl p-4 border-glow">
          <p className="text-xs font-semibold text-bravo-muted uppercase tracking-wider">Benchmark</p>
          <p className="font-medium mt-1 text-sunset-400">
            {prompt.benchmark_score ? `${prompt.benchmark_score.toFixed(1)}%` : '—'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Content */}
        <div className="lg:col-span-2">
          <div className="glass rounded-xl border-glow">
            <div className="flex items-center justify-between p-4 border-b border-bravo-border">
              <h2 className="font-semibold text-bravo-text">Content</h2>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 text-sm text-bravo-muted hover:text-sunset-400 transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4 text-sunset-400" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" /> Copy
                  </>
                )}
              </button>
            </div>
            <pre className="p-4 overflow-x-auto text-sm font-mono text-bravo-text-secondary whitespace-pre-wrap bg-bravo-elevated/30">
              {prompt.content}
            </pre>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Version History */}
          <div className="glass rounded-xl border-glow">
            <div className="flex items-center justify-between p-4 border-b border-bravo-border">
              <h2 className="font-semibold flex items-center gap-2 text-bravo-text">
                <GitBranch className="w-4 h-4 text-sunset-500" /> Version History
              </h2>
            </div>
            <div className="divide-y divide-bravo-border-subtle">
              {versions.slice(0, 5).map((version) => (
                <div key={version.id} className="p-4 hover:bg-bravo-elevated/30 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm text-sunset-500">{version.version}</span>
                    <span className="text-xs text-bravo-muted">
                      {new Date(version.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {version.change_summary && (
                    <p className="text-sm text-bravo-muted mt-1">{version.change_summary}</p>
                  )}
                </div>
              ))}
              {versions.length === 0 && (
                <p className="p-4 text-sm text-bravo-muted">No version history</p>
              )}
            </div>
          </div>

          {/* Tags */}
          {prompt.tags && prompt.tags.length > 0 && (
            <div className="glass rounded-xl p-4 border-glow">
              <h2 className="font-semibold mb-3 text-bravo-text">Tags</h2>
              <div className="flex flex-wrap gap-2">
                {prompt.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2.5 py-1 text-xs bg-sunset-500/10 text-sunset-400 border border-sunset-800/30 rounded-full font-medium"
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
