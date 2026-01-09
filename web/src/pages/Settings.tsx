import { useState } from 'react';
import {
  User,
  Key,
  Bell,
  Link,
  Shield,
  Save,
} from 'lucide-react';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('profile');

  const tabs = [
    { id: 'profile', name: 'Profile', icon: User },
    { id: 'api', name: 'API Keys', icon: Key },
    { id: 'notifications', name: 'Notifications', icon: Bell },
    { id: 'integrations', name: 'Integrations', icon: Link },
    { id: 'security', name: 'Security', icon: Shield },
  ];

  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-slate-400 mt-1">Manage your account and preferences</p>
      </div>

      <div className="flex gap-8">
        {/* Sidebar */}
        <div className="w-56">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  activeTab === tab.id
                    ? 'bg-sunset-500/20 text-sunset-400'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                <span>{tab.name}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'profile' && (
            <div className="glass rounded-xl p-6">
              <h2 className="text-xl font-semibold mb-6">Profile Settings</h2>
              <div className="space-y-4 max-w-lg">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    Display Name
                  </label>
                  <input
                    type="text"
                    defaultValue="Developer"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    Email
                  </label>
                  <input
                    type="email"
                    defaultValue="developer@bravozero.ai"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg focus:border-sunset-500 focus:ring-1 focus:ring-sunset-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    Organization
                  </label>
                  <input
                    type="text"
                    defaultValue="Bravo Zero"
                    disabled
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg opacity-50"
                  />
                </div>
                <button className="flex items-center gap-2 px-4 py-2 bg-sunset-500 hover:bg-sunset-600 rounded-lg transition-colors mt-6">
                  <Save className="w-4 h-4" />
                  <span>Save Changes</span>
                </button>
              </div>
            </div>
          )}

          {activeTab === 'api' && (
            <div className="glass rounded-xl p-6">
              <h2 className="text-xl font-semibold mb-6">API Keys</h2>
              <p className="text-slate-400 mb-4">
                Manage API keys for programmatic access to Hermes.
              </p>
              <button className="flex items-center gap-2 px-4 py-2 bg-sunset-500 hover:bg-sunset-600 rounded-lg transition-colors">
                <Key className="w-4 h-4" />
                <span>Generate New Key</span>
              </button>
              <div className="mt-6 p-4 bg-slate-800 rounded-lg">
                <p className="text-sm text-slate-400">No API keys generated yet.</p>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="glass rounded-xl p-6">
              <h2 className="text-xl font-semibold mb-6">Notification Settings</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-slate-800 rounded-lg">
                  <div>
                    <p className="font-medium">Benchmark Alerts</p>
                    <p className="text-sm text-slate-400">
                      Get notified when benchmark scores change
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" defaultChecked className="sr-only peer" />
                    <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sunset-500"></div>
                  </label>
                </div>
                <div className="flex items-center justify-between p-4 bg-slate-800 rounded-lg">
                  <div>
                    <p className="font-medium">Deployment Updates</p>
                    <p className="text-sm text-slate-400">
                      Notifications when prompts are deployed
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" defaultChecked className="sr-only peer" />
                    <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sunset-500"></div>
                  </label>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="glass rounded-xl p-6">
              <h2 className="text-xl font-semibold mb-6">Integrations</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
                      <span className="text-purple-400 font-bold">A</span>
                    </div>
                    <div>
                      <p className="font-medium">ATE Benchmarking</p>
                      <p className="text-sm text-slate-400">Connected</p>
                    </div>
                  </div>
                  <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded-full">
                    Active
                  </span>
                </div>
                <div className="flex items-center justify-between p-4 bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
                      <span className="text-blue-400 font-bold">S</span>
                    </div>
                    <div>
                      <p className="font-medium">ASRBS Self-Critique</p>
                      <p className="text-sm text-slate-400">Connected</p>
                    </div>
                  </div>
                  <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded-full">
                    Active
                  </span>
                </div>
                <div className="flex items-center justify-between p-4 bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
                      <span className="text-orange-400 font-bold">B</span>
                    </div>
                    <div>
                      <p className="font-medium">Beeper Notifications</p>
                      <p className="text-sm text-slate-400">Connected</p>
                    </div>
                  </div>
                  <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded-full">
                    Active
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="glass rounded-xl p-6">
              <h2 className="text-xl font-semibold mb-6">Security</h2>
              <div className="space-y-4">
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="font-medium">Single Sign-On</p>
                  <p className="text-sm text-slate-400 mt-1">
                    Authenticated via PERSONA SSO
                  </p>
                </div>
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="font-medium">Sessions</p>
                  <p className="text-sm text-slate-400 mt-1">
                    1 active session
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
