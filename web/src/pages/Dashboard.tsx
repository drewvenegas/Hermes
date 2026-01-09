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

export default function Dashboard() {
  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-slate-400 mt-1">Welcome to Hermes Prompt Engineering Platform</p>
        </div>
        <Link
          to="/prompts/new"
          className="flex items-center gap-2 px-4 py-2 bg-sunset-500 hover:bg-sunset-600 rounded-lg transition-colors"
        >
          <Plus className="w-5 h-5" />
          <span>New Prompt</span>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat) => (
          <div key={stat.name} className="glass rounded-xl p-6 animate-slide-up">
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-sunset-500/20">
                <stat.icon className="w-5 h-5 text-sunset-400" />
              </div>
              <span className={`text-sm font-medium ${
                stat.changeType === 'increase' ? 'text-green-400' : 'text-red-400'
              }`}>
                {stat.change}
              </span>
            </div>
            <div className="mt-4">
              <p className="text-2xl font-bold">{stat.value}</p>
              <p className="text-sm text-slate-400">{stat.name}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Prompts */}
      <div className="glass rounded-xl">
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <h2 className="text-lg font-semibold">Recent Prompts</h2>
          <Link to="/prompts" className="flex items-center gap-1 text-sm text-sunset-400 hover:text-sunset-300">
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="divide-y divide-slate-700">
          {recentPrompts.map((prompt) => (
            <Link
              key={prompt.id}
              to={`/prompts/${prompt.id}`}
              className="flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-slate-700 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-slate-400" />
                </div>
                <div>
                  <p className="font-medium">{prompt.name}</p>
                  <p className="text-sm text-slate-400">{prompt.type.replace('_', ' ')}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="font-medium">{prompt.score}%</p>
                  <p className="text-xs text-slate-400">Benchmark</p>
                </div>
                <span className={`px-2 py-1 text-xs rounded-full ${
                  prompt.status === 'deployed' ? 'bg-green-500/20 text-green-400' :
                  prompt.status === 'staged' ? 'bg-blue-500/20 text-blue-400' :
                  'bg-yellow-500/20 text-yellow-400'
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
