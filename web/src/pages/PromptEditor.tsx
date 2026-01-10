import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import {
  Save,
  Play,
  History,
  ArrowLeft,
  ChevronDown,
} from 'lucide-react';
import { api } from '../services/api';

interface PromptData {
  slug: string;
  name: string;
  description: string;
  type: string;
  category: string;
  content: string;
  visibility: string;
}

const promptTypes = [
  { value: 'agent_system', label: 'Agent System Prompt' },
  { value: 'user_template', label: 'User Template' },
  { value: 'tool_definition', label: 'Tool Definition' },
  { value: 'mcp_instruction', label: 'MCP Instruction' },
];

export default function PromptEditor() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEditing = Boolean(id);

  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<PromptData>({
    slug: '',
    name: '',
    description: '',
    type: 'agent_system',
    category: '',
    content: '# Enter your prompt here\n\nYou are a helpful AI assistant.',
    visibility: 'private',
  });

  useEffect(() => {
    if (id) {
      loadPrompt(id);
    }
  }, [id]);

  const loadPrompt = async (promptId: string) => {
    try {
      const prompt = await api.getPrompt(promptId);
      setData({
        slug: prompt.slug,
        name: prompt.name,
        description: prompt.description || '',
        type: prompt.type,
        category: prompt.category || '',
        content: prompt.content,
        visibility: prompt.visibility,
      });
    } catch (error) {
      console.error('Failed to load prompt:', error);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      if (isEditing && id) {
        await api.updatePrompt(id, data);
      } else {
        await api.createPrompt(data);
      }
      navigate('/prompts');
    } catch (error) {
      console.error('Failed to save prompt:', error);
    } finally {
      setSaving(false);
    }
  };

  const generateSlug = (name: string) => {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  };

  return (
    <div className="h-full flex flex-col animate-fade-in bg-bravo-bg">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-bravo-border bg-bravo-surface">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-bravo-elevated rounded-lg transition-colors text-bravo-muted hover:text-bravo-text"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-semibold bg-gradient-to-r from-sunset-300 to-sunset-500 bg-clip-text text-transparent">
              {isEditing ? 'Edit Prompt' : 'New Prompt'}
            </h1>
            <p className="text-sm text-bravo-muted">
              {isEditing ? data.name : 'Create a new prompt'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2.5 bg-bravo-elevated border border-bravo-border hover:border-sunset-800 rounded-lg transition-colors text-bravo-text-secondary">
            <History className="w-4 h-4" />
            <span>History</span>
          </button>
          <button className="flex items-center gap-2 px-4 py-2.5 bg-bravo-elevated border border-bravo-border hover:border-sunset-800 rounded-lg transition-colors text-bravo-text-secondary">
            <Play className="w-4 h-4" />
            <span>Benchmark</span>
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-sunset hover:opacity-90 rounded-lg transition-all shadow-sunset text-white font-medium disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save'}</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-80 border-r border-bravo-border p-4 overflow-y-auto bg-bravo-surface">
          <div className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-bravo-text-secondary mb-1">Name</label>
              <input
                type="text"
                value={data.name}
                onChange={(e) => {
                  const name = e.target.value;
                  setData((prev) => ({
                    ...prev,
                    name,
                    slug: isEditing ? prev.slug : generateSlug(name),
                  }));
                }}
                className="w-full px-3 py-2.5 bg-bravo-elevated border border-bravo-border rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none text-bravo-text placeholder-bravo-muted transition-colors"
                placeholder="My Awesome Prompt"
              />
            </div>

            {/* Slug */}
            <div>
              <label className="block text-sm font-medium text-bravo-text-secondary mb-1">Slug</label>
              <input
                type="text"
                value={data.slug}
                onChange={(e) => setData((prev) => ({ ...prev, slug: e.target.value }))}
                disabled={isEditing}
                className="w-full px-3 py-2.5 bg-bravo-elevated border border-bravo-border rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none disabled:opacity-50 text-bravo-text font-mono placeholder-bravo-muted transition-colors"
                placeholder="my-awesome-prompt"
              />
            </div>

            {/* Type */}
            <div>
              <label className="block text-sm font-medium text-bravo-text-secondary mb-1">Type</label>
              <div className="relative">
                <select
                  value={data.type}
                  onChange={(e) => setData((prev) => ({ ...prev, type: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-bravo-elevated border border-bravo-border rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none appearance-none text-bravo-text transition-colors"
                >
                  {promptTypes.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-bravo-muted pointer-events-none" />
              </div>
            </div>

            {/* Category */}
            <div>
              <label className="block text-sm font-medium text-bravo-text-secondary mb-1">Category</label>
              <input
                type="text"
                value={data.category}
                onChange={(e) => setData((prev) => ({ ...prev, category: e.target.value }))}
                className="w-full px-3 py-2.5 bg-bravo-elevated border border-bravo-border rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none text-bravo-text placeholder-bravo-muted transition-colors"
                placeholder="agents, tools, templates..."
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-bravo-text-secondary mb-1">Description</label>
              <textarea
                value={data.description}
                onChange={(e) => setData((prev) => ({ ...prev, description: e.target.value }))}
                rows={3}
                className="w-full px-3 py-2.5 bg-bravo-elevated border border-bravo-border rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none resize-none text-bravo-text placeholder-bravo-muted transition-colors"
                placeholder="Describe what this prompt does..."
              />
            </div>

            {/* Visibility */}
            <div>
              <label className="block text-sm font-medium text-bravo-text-secondary mb-1">Visibility</label>
              <div className="relative">
                <select
                  value={data.visibility}
                  onChange={(e) => setData((prev) => ({ ...prev, visibility: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-bravo-elevated border border-bravo-border rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none appearance-none text-bravo-text transition-colors"
                >
                  <option value="private">Private</option>
                  <option value="team">Team</option>
                  <option value="organization">Organization</option>
                  <option value="public">Public</option>
                </select>
                <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-bravo-muted pointer-events-none" />
              </div>
            </div>
          </div>
        </div>

        {/* Editor */}
        <div className="flex-1 overflow-hidden bg-bravo-elevated">
          <Editor
            height="100%"
            language="markdown"
            theme="vs-dark"
            value={data.content}
            onChange={(value) => setData((prev) => ({ ...prev, content: value || '' }))}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineHeight: 22,
              padding: { top: 16, bottom: 16 },
              wordWrap: 'on',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          />
        </div>
      </div>
    </div>
  );
}
