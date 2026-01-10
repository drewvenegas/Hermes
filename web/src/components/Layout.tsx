import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Settings,
  Zap,
  User,
  LogOut,
  BarChart3,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Prompts', href: '/prompts', icon: FileText },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export default function Layout() {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-bravo-bg">
      {/* Sidebar - Warm Dark Theme */}
      <aside className="w-64 bg-bravo-surface border-r border-bravo-border flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-bravo-border">
          <div className="w-8 h-8 rounded-lg bg-gradient-sunset flex items-center justify-center shadow-sunset">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-semibold bg-gradient-to-r from-sunset-400 to-sunset-600 bg-clip-text text-transparent">
            Hermes
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href ||
              (item.href !== '/' && location.pathname.startsWith(item.href));
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-sunset-500/15 text-sunset-400 border border-sunset-800/50'
                    : 'text-bravo-muted hover:bg-bravo-elevated hover:text-bravo-text border border-transparent'
                }`}
              >
                <item.icon className={`w-5 h-5 ${isActive ? 'text-sunset-500' : ''}`} />
                <span className="font-medium">{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Section */}
        <div className="p-4 border-t border-bravo-border">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-bravo-elevated border border-bravo-border-subtle">
            <div className="w-8 h-8 rounded-full bg-gradient-sunset flex items-center justify-center shadow-sunset">
              <User className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate text-bravo-text">Developer</p>
              <p className="text-xs text-bravo-muted truncate">Bravo Zero</p>
            </div>
            <button className="text-bravo-muted hover:text-sunset-400 transition-colors">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 overflow-auto bg-bravo-bg">
        <Outlet />
      </main>
    </div>
  );
}
