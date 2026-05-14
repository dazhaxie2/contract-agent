import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Spin } from 'antd';

import MainLayout from './components/Layout/MainLayout';

const LoginPage = lazy(() => import('./pages/Auth/LoginPage'));
const ChatPage = lazy(() => import('./pages/Chat/ChatPage'));
const ReviewWorkspace = lazy(() => import('./pages/Reviews/ReviewWorkspace'));
const DocumentLibrary = lazy(() => import('./pages/Documents/DocumentLibrary'));
const SystemDashboard = lazy(() => import('./pages/Dashboard/SystemDashboard'));
const AgentTraceDashboard = lazy(() => import('./pages/Dashboard/AgentTraceDashboard'));
const RetrievalDashboard = lazy(() => import('./pages/Dashboard/RetrievalDashboard'));
const ModelConfigList = lazy(() => import('./pages/ModelConfig/ModelConfigList'));
const ModelConfigForm = lazy(() => import('./pages/ModelConfig/ModelConfigForm'));
const ModelConfigDetail = lazy(() => import('./pages/ModelConfig/ModelConfigDetail'));
const ModelDeployment = lazy(() => import('./pages/ModelConfig/ModelDeployment'));
const ABTestPanel = lazy(() => import('./pages/ModelConfig/ABTestPanel'));
const PromptList = lazy(() => import('./pages/PromptManager/PromptList'));
const PromptEditor = lazy(() => import('./pages/PromptManager/PromptEditor'));
const PromptVersionHistory = lazy(() => import('./pages/PromptManager/PromptVersionHistory'));
const PromptTestPanel = lazy(() => import('./pages/PromptManager/PromptTestPanel'));

const routeFallback = (
  <div style={{ minHeight: 240, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <Spin />
  </div>
);

const App: React.FC = () => (
  <BrowserRouter>
    <Suspense fallback={routeFallback}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/chat" replace />} />

          <Route path="chat" element={<ChatPage />} />
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
    </Suspense>
  </BrowserRouter>
);

export default App;
