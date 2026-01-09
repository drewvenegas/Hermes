import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import PromptList from './pages/PromptList';
import PromptEditor from './pages/PromptEditor';
import PromptDetail from './pages/PromptDetail';
import Settings from './pages/Settings';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="prompts" element={<PromptList />} />
        <Route path="prompts/new" element={<PromptEditor />} />
        <Route path="prompts/:id" element={<PromptDetail />} />
        <Route path="prompts/:id/edit" element={<PromptEditor />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default App;
