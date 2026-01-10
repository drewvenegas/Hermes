import { Link } from 'react-router-dom';
import {
  FileText,
  TrendingUp,
  Clock,
  AlertTriangle,
  Plus,
  ArrowRight,
} from 'lucide-react';

const stats = [
  { name: 'Total Prompts', value: '127', icon: FileText, change: '+12', changeType: 'increase' },
  { name: 'Avg. Benchmark', value: '87.3', icon: TrendingUp, change: '+2.1', changeType: 'increase' },
  { name: 'Deployments', value: '23', icon: Clock, change: '+5', changeType: 'increase' },
  { name: 'Issues', value: '3', icon: AlertTriangle, change: '-2', changeType: 'decrease' },
];

const recentPrompts = [
  { id: '1', name: 'ARIA Core Agent', type: 'agent_system', score: 92.5, status: 'deployed' },
  { id: '2', name: 'Code Review Template', type: 'user_template', score: 88.1, status: 'staged' },
  { id: '3', name: 'Tool: Web Search', type: 'tool_definition', score: 85.7, status: 'review' },
  { id: '4', name: 'MCP Browser Control', type: 'mcp_instruction', score: 90.2, status: 'deployed' },
];

// Monochromatic status variants - different intensities of sunset orange
const statusStyles: Record<string, string> = {
  deployed: 'bg-sunset-500/20 text-sunset-400 border border-sunset-700/50',
  staged: 'bg-sunset-600/15 text-sunset-500 border border-sunset-800/50',
  review: 'bg-sunset-700/15 text-sunset-600 border border-sunset-900/50',
  draft: 'bg-bravo-elevated text-bravo-muted border border-bravo-border-subtle',
};

export default function Dashboard() {
  return (
    <div className="p-8 animate-fade-in bg-bravo-bg min-h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-sunset-300 to-sunset-500 bg-clip-text text-transparent">
            Dashboard
          </h1>
          <p className="text-bravo-muted mt-1">Welcome to Hermes Prompt Engineering Platform</p>
        </div>
        <Link
          to="/prompts/new"
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-sunset hover:opacity-90 rounded-lg transition-all shadow-sunset text-white font-medium"
        >
          <Plus className="w-5 h-5" />
          <span>New Prompt</span>
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        {stats.map((stat, index) => (
          <div 
            key={stat.name} 
            className="glass rounded-xl p-6 animate-slide-up border-glow"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-lg bg-sunset-500/15 border border-sunset-800/30">
                <stat.icon className="w-5 h-5 text-sunset-400" />
              </div>
              <span className={`text-sm font-semibold ${
                stat.changeType === 'increase' 
                  ? 'text-sunset-400' 
                  : 'text-sunset-700'
              }`}>
                {stat.change}
              </span>
            </div>
            <div className="mt-4">
              <p className="text-3xl font-bold text-bravo-text">{stat.value}</p>
              <p className="text-sm text-bravo-muted mt-1">{stat.name}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Prompts Table */}
      <div className="glass rounded-xl border-glow">
        <div className="flex items-center justify-between p-6 border-b border-bravo-border">
          <h2 className="text-lg font-semibold text-bravo-text">Recent Prompts</h2>
          <Link 
            to="/prompts" 
            className="flex items-center gap-1 text-sm text-sunset-400 hover:text-sunset-300 transition-colors font-medium"
          >
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="divide-y divide-bravo-border-subtle">
          {recentPrompts.map((prompt) => (
            <Link
              key={prompt.id}
              to={`/prompts/${prompt.id}`}
              className="flex items-center justify-between p-4 hover:bg-bravo-elevated/50 transition-colors group"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-bravo-elevated border border-bravo-border-subtle flex items-center justify-center group-hover:border-sunset-800 transition-colors">
                  <FileText className="w-5 h-5 text-bravo-muted group-hover:text-sunset-500 transition-colors" />
                </div>
                <div>
                  <p className="font-medium text-bravo-text group-hover:text-sunset-400 transition-colors">
                    {prompt.name}
                  </p>
                  <p className="text-sm text-bravo-muted">{prompt.type.replace('_', ' ')}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="font-semibold text-sunset-400">{prompt.score}%</p>
                  <p className="text-xs text-bravo-muted">Benchmark</p>
                </div>
                <span className={`px-2.5 py-1 text-xs rounded-full font-medium ${
                  statusStyles[prompt.status] || statusStyles.draft
                }`}>
                  {prompt.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
