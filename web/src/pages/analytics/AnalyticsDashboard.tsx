/**
 * Analytics Dashboard
 * 
 * Main dashboard for viewing Hermes analytics, benchmark trends,
 * and experiment results.
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Container,
  Grid,
  Paper,
  Tab,
  Tabs,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Chip,
} from '@mui/material';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Assessment,
  Speed,
  CheckCircle,
  Science,
} from '@mui/icons-material';

// Types
interface OverviewMetrics {
  totalPrompts: number;
  totalBenchmarks: number;
  averageScore: number;
  scoreChange: number;
  passRate: number;
  activeExperiments: number;
}

interface BenchmarkTrend {
  date: string;
  avgScore: number;
  totalRuns: number;
  passRate: number;
}

interface CategoryBreakdown {
  category: string;
  count: number;
  avgScore: number;
}

interface ExperimentSummary {
  id: string;
  name: string;
  status: string;
  variants: number;
  sampleSize: number;
  winningVariant?: string;
}

// Mock data - in production, fetch from Hermes API
const mockOverview: OverviewMetrics = {
  totalPrompts: 147,
  totalBenchmarks: 1234,
  averageScore: 0.847,
  scoreChange: 0.023,
  passRate: 0.923,
  activeExperiments: 3,
};

const mockTrends: BenchmarkTrend[] = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
  avgScore: 0.8 + Math.random() * 0.1,
  totalRuns: Math.floor(20 + Math.random() * 30),
  passRate: 0.85 + Math.random() * 0.1,
}));

const mockCategories: CategoryBreakdown[] = [
  { category: 'Agent System', count: 32, avgScore: 0.89 },
  { category: 'User Template', count: 45, avgScore: 0.82 },
  { category: 'Tool Definition', count: 38, avgScore: 0.86 },
  { category: 'MCP Instruction', count: 32, avgScore: 0.84 },
];

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

// Metric Card Component
interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: number;
  subtitle?: string;
}

function MetricCard({ title, value, icon, trend, subtitle }: MetricCardProps) {
  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography color="text.secondary" variant="body2" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h4" component="div">
              {value}
            </Typography>
            {trend !== undefined && (
              <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                {trend >= 0 ? (
                  <TrendingUp color="success" fontSize="small" />
                ) : (
                  <TrendingDown color="error" fontSize="small" />
                )}
                <Typography
                  variant="body2"
                  color={trend >= 0 ? 'success.main' : 'error.main'}
                  sx={{ ml: 0.5 }}
                >
                  {trend >= 0 ? '+' : ''}{(trend * 100).toFixed(1)}%
                </Typography>
              </Box>
            )}
            {subtitle && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box sx={{ color: 'primary.main', opacity: 0.8 }}>
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

// Main Component
export function AnalyticsDashboard() {
  const [timeRange, setTimeRange] = useState('30d');
  const [isLoading, setIsLoading] = useState(false);
  const [overview, setOverview] = useState<OverviewMetrics>(mockOverview);
  const [trends, setTrends] = useState<BenchmarkTrend[]>(mockTrends);
  const [categories, setCategories] = useState<CategoryBreakdown[]>(mockCategories);

  // In production, fetch data here
  useEffect(() => {
    // fetchAnalytics(timeRange);
  }, [timeRange]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" component="h1">
          Analytics Dashboard
        </Typography>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Time Range</InputLabel>
          <Select
            value={timeRange}
            label="Time Range"
            onChange={(e) => setTimeRange(e.target.value)}
          >
            <MenuItem value="7d">Last 7 Days</MenuItem>
            <MenuItem value="30d">Last 30 Days</MenuItem>
            <MenuItem value="90d">Last 90 Days</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Overview Metrics */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Prompts"
            value={overview.totalPrompts}
            icon={<Assessment sx={{ fontSize: 40 }} />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Benchmark Runs"
            value={overview.totalBenchmarks.toLocaleString()}
            icon={<Speed sx={{ fontSize: 40 }} />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Average Score"
            value={`${(overview.averageScore * 100).toFixed(1)}%`}
            icon={<TrendingUp sx={{ fontSize: 40 }} />}
            trend={overview.scoreChange}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Gate Pass Rate"
            value={`${(overview.passRate * 100).toFixed(1)}%`}
            icon={<CheckCircle sx={{ fontSize: 40 }} />}
            subtitle={`${overview.activeExperiments} active experiments`}
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3}>
        {/* Score Trends */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardHeader title="Benchmark Score Trends" />
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={trends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  />
                  <YAxis domain={[0.7, 1]} tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} />
                  <Tooltip
                    formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="avgScore"
                    name="Average Score"
                    stroke="#8884d8"
                    fill="#8884d8"
                    fillOpacity={0.3}
                  />
                  <Area
                    type="monotone"
                    dataKey="passRate"
                    name="Pass Rate"
                    stroke="#82ca9d"
                    fill="#82ca9d"
                    fillOpacity={0.3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Category Distribution */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardHeader title="Prompts by Category" />
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={categories}
                    dataKey="count"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ category, percent }) => `${category}: ${(percent * 100).toFixed(0)}%`}
                  >
                    {categories.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Daily Benchmark Runs */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Daily Benchmark Runs" />
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={trends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { day: 'numeric' })}
                  />
                  <YAxis />
                  <Tooltip
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Bar dataKey="totalRuns" name="Benchmark Runs" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Category Performance */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Category Performance" />
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={categories} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                  <YAxis type="category" dataKey="category" width={100} />
                  <Tooltip formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
                  <Bar dataKey="avgScore" name="Avg Score" fill="#82ca9d" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
}

export default AnalyticsDashboard;
