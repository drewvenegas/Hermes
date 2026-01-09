import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface TimeSeriesPoint {
  timestamp: string;
  value: number;
  label?: string;
}

interface DashboardData {
  total_prompts: number;
  total_users: number;
  total_benchmarks: number;
  avg_benchmark_score: number;
  prompts_this_week: number;
  benchmarks_this_week: number;
  top_prompts: Array<{
    id: string;
    slug: string;
    name: string;
    benchmark_score?: number;
    usage_count?: number;
  }>;
  benchmark_trends: TimeSeriesPoint[];
  activity_by_type: Record<string, number>;
  model_usage: Record<string, number>;
}

interface UserStats {
  prompts_created: number;
  benchmarks_run: number;
  reviews_submitted: number;
  comments_made: number;
  activity_count: number;
  period_days: number;
}

function StatCard({ title, value, subtitle, trend }: {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'neutral';
}) {
  return (
    <div className="stat-card">
      <div className="stat-card-header">
        <span className="stat-title">{title}</span>
        {trend && (
          <span className={`trend-indicator ${trend}`}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
          </span>
        )}
      </div>
      <div className="stat-value">{value}</div>
      {subtitle && <div className="stat-subtitle">{subtitle}</div>}
    </div>
  );
}

function SimpleBarChart({ data, title }: {
  data: Record<string, number>;
  title: string;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const maxValue = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="chart-container">
      <h3 className="chart-title">{title}</h3>
      <div className="bar-chart">
        {entries.map(([label, value]) => (
          <div key={label} className="bar-row">
            <div className="bar-label">{label}</div>
            <div className="bar-track">
              <div 
                className="bar-fill" 
                style={{ width: `${(value / maxValue) * 100}%` }}
              />
            </div>
            <div className="bar-value">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendChart({ data, title }: {
  data: TimeSeriesPoint[];
  title: string;
}) {
  if (data.length === 0) {
    return (
      <div className="chart-container">
        <h3 className="chart-title">{title}</h3>
        <div className="empty-chart">No data available</div>
      </div>
    );
  }

  const values = data.map(d => d.value);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = maxValue - minValue || 1;

  // Generate SVG path
  const width = 600;
  const height = 200;
  const padding = 40;
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;

  const points = data.map((point, i) => {
    const x = padding + (i / (data.length - 1 || 1)) * chartWidth;
    const y = height - padding - ((point.value - minValue) / range) * chartHeight;
    return { x, y, value: point.value, date: point.timestamp };
  });

  const pathD = points.map((p, i) => 
    `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
  ).join(' ');

  return (
    <div className="chart-container trend-chart">
      <h3 className="chart-title">{title}</h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="line-chart-svg">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => (
          <g key={i}>
            <line
              x1={padding}
              y1={padding + ratio * chartHeight}
              x2={width - padding}
              y2={padding + ratio * chartHeight}
              className="grid-line"
            />
            <text
              x={padding - 5}
              y={padding + ratio * chartHeight + 4}
              className="axis-label"
              textAnchor="end"
            >
              {(maxValue - ratio * range).toFixed(0)}
            </text>
          </g>
        ))}
        
        {/* Line path */}
        <path d={pathD} className="trend-line" fill="none" />
        
        {/* Data points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r="4"
            className="data-point"
          >
            <title>{`${new Date(p.date).toLocaleDateString()}: ${p.value.toFixed(1)}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

function TopPromptsTable({ prompts }: {
  prompts: Array<{
    id: string;
    slug: string;
    name: string;
    benchmark_score?: number;
  }>;
}) {
  return (
    <div className="table-container">
      <h3 className="table-title">Top Prompts by Score</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Slug</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {prompts.map((prompt) => (
            <tr key={prompt.id}>
              <td>{prompt.name}</td>
              <td><code>{prompt.slug}</code></td>
              <td>
                <span className={`score-badge ${
                  (prompt.benchmark_score || 0) >= 80 ? 'good' :
                  (prompt.benchmark_score || 0) >= 60 ? 'medium' : 'low'
                }`}>
                  {prompt.benchmark_score?.toFixed(1) || 'N/A'}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Analytics() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'benchmarks' | 'activity'>('overview');

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const [dashboardRes, userStatsRes] = await Promise.all([
          api.get('/analytics/dashboard'),
          api.get('/analytics/user?days=30'),
        ]);
        setDashboard(dashboardRes.data);
        setUserStats(userStatsRes.data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch analytics:', err);
        setError('Failed to load analytics data');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="analytics-page">
        <div className="loading-spinner">Loading analytics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="analytics-page">
        <div className="error-message">{error}</div>
      </div>
    );
  }

  return (
    <div className="analytics-page">
      <header className="page-header">
        <h1>Analytics Dashboard</h1>
        <p className="page-subtitle">Insights into your prompt engineering workflow</p>
      </header>

      <nav className="analytics-tabs">
        <button
          className={`tab-button ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`tab-button ${activeTab === 'benchmarks' ? 'active' : ''}`}
          onClick={() => setActiveTab('benchmarks')}
        >
          Benchmarks
        </button>
        <button
          className={`tab-button ${activeTab === 'activity' ? 'active' : ''}`}
          onClick={() => setActiveTab('activity')}
        >
          Activity
        </button>
      </nav>

      {activeTab === 'overview' && dashboard && (
        <div className="tab-content">
          <div className="stats-grid">
            <StatCard
              title="Total Prompts"
              value={dashboard.total_prompts}
              subtitle={`+${dashboard.prompts_this_week} this week`}
              trend="up"
            />
            <StatCard
              title="Total Benchmarks"
              value={dashboard.total_benchmarks}
              subtitle={`+${dashboard.benchmarks_this_week} this week`}
              trend="up"
            />
            <StatCard
              title="Avg Benchmark Score"
              value={`${dashboard.avg_benchmark_score.toFixed(1)}%`}
              trend={dashboard.avg_benchmark_score >= 80 ? 'up' : 'neutral'}
            />
            <StatCard
              title="Active Users"
              value={dashboard.total_users}
            />
          </div>

          <div className="charts-grid">
            <TrendChart 
              data={dashboard.benchmark_trends} 
              title="Benchmark Scores (30 days)"
            />
            <TopPromptsTable prompts={dashboard.top_prompts} />
          </div>

          <div className="charts-row">
            <SimpleBarChart 
              data={dashboard.model_usage} 
              title="Benchmark Runs by Model"
            />
            <SimpleBarChart 
              data={dashboard.activity_by_type} 
              title="Activity by Type"
            />
          </div>
        </div>
      )}

      {activeTab === 'benchmarks' && dashboard && (
        <div className="tab-content">
          <div className="stats-grid">
            <StatCard
              title="Total Benchmark Runs"
              value={dashboard.total_benchmarks}
            />
            <StatCard
              title="Avg Score"
              value={`${dashboard.avg_benchmark_score.toFixed(1)}%`}
            />
            <StatCard
              title="This Week"
              value={dashboard.benchmarks_this_week}
            />
          </div>

          <TrendChart 
            data={dashboard.benchmark_trends} 
            title="Benchmark Score Trend"
          />

          <SimpleBarChart 
            data={dashboard.model_usage} 
            title="Runs by Model"
          />
        </div>
      )}

      {activeTab === 'activity' && userStats && (
        <div className="tab-content">
          <h2>Your Activity (Last {userStats.period_days} Days)</h2>
          
          <div className="stats-grid">
            <StatCard
              title="Prompts Created"
              value={userStats.prompts_created}
            />
            <StatCard
              title="Benchmarks Run"
              value={userStats.benchmarks_run}
            />
            <StatCard
              title="Reviews Submitted"
              value={userStats.reviews_submitted}
            />
            <StatCard
              title="Comments Made"
              value={userStats.comments_made}
            />
          </div>

          <div className="activity-summary">
            <p>Total activities: <strong>{userStats.activity_count}</strong></p>
          </div>

          {dashboard && (
            <SimpleBarChart 
              data={dashboard.activity_by_type} 
              title="Team Activity by Type"
            />
          )}
        </div>
      )}
    </div>
  );
}
