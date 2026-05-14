import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import MainLayout from './components/Layout/MainLayout';
import LoginPage from './pages/Auth/LoginPage';
import ReviewWorkspace from './pages/Reviews/ReviewWorkspace';
import DocumentLibrary from './pages/Documents/DocumentLibrary';
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

const App: React.FC = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Navigate to="/reviews" replace />} />

        <Route path="reviews" element={<ReviewWorkspace />} />
        <Route path="documents" element={<DocumentLibrary />} />

        <Route path="dashboard" element={<SystemDashboard />} />
        <Route path="dashboard/agent-trace" element={<AgentTraceDashboard />} />
        <Route path="dashboard/retrieval" element={<RetrievalDashboard />} />

        <Route path="models" element={<ModelConfigList />} />
        <Route path="models/create" element={<ModelConfigForm />} />
        <Route path="models/:id/edit" element={<ModelConfigForm />} />
        <Route path="models/:id" element={<ModelConfigDetail />} />
        <Route path="models/deployment" element={<ModelDeployment />} />
        <Route path="models/ab-test" element={<ABTestPanel />} />

        <Route path="prompts" element={<PromptList />} />
        <Route path="prompts/create" element={<PromptEditor />} />
        <Route path="prompts/:id/edit" element={<PromptEditor />} />
        <Route path="prompts/:id/history" element={<PromptVersionHistory />} />
        <Route path="prompts/test" element={<PromptTestPanel />} />
      </Route>
    </Routes>
  </BrowserRouter>
);

export default App;
