import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './components/Layout/MainLayout';
import SystemDashboard from './pages/Dashboard/SystemDashboard';
import AgentTraceDashboard from './pages/Dashboard/AgentTraceDashboard';
import RetrievalDashboard from './pages/Dashboard/RetrievalDashboard';
import ModelConfigList from './pages/ModelConfig/ModelConfigList';
import ModelConfigForm from './pages/ModelConfig/ModelConfigForm';
import ModelConfigDetail from './pages/ModelConfig/ModelConfigDetail';
import ModelDeployment from './pages/ModelConfig/ModelDeployment';
import ABTestPanel from './pages/ModelConfig/ABTestPanel';
import PromptList from './pages/PromptManager/PromptList';
import PromptEditor from './pages/PromptManager/PromptEditor';
import PromptVersionHistory from './pages/PromptManager/PromptVersionHistory';
import PromptTestPanel from './pages/PromptManager/PromptTestPanel';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />

          {/* 监控大盘 */}
          <Route path="dashboard" element={<SystemDashboard />} />
          <Route path="dashboard/agent-trace" element={<AgentTraceDashboard />} />
          <Route path="dashboard/retrieval" element={<RetrievalDashboard />} />

          {/* 模型配置 */}
          <Route path="models" element={<ModelConfigList />} />
          <Route path="models/create" element={<ModelConfigForm />} />
          <Route path="models/:id/edit" element={<ModelConfigForm />} />
          <Route path="models/:id" element={<ModelConfigDetail />} />
          <Route path="models/deployment" element={<ModelDeployment />} />
          <Route path="models/ab-test" element={<ABTestPanel />} />

          {/* 提示词管理 */}
          <Route path="prompts" element={<PromptList />} />
          <Route path="prompts/create" element={<PromptEditor />} />
          <Route path="prompts/:id/edit" element={<PromptEditor />} />
          <Route path="prompts/:id/history" element={<PromptVersionHistory />} />
          <Route path="prompts/test" element={<PromptTestPanel />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
