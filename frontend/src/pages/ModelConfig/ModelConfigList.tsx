import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Card, Button, Tag, Space, Input, Select, Typography, Popconfirm, message, Badge } from 'antd';
import { PlusOutlined, SearchOutlined, SettingOutlined, EyeOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';

const { Title } = Typography;

const providerColors: Record<string, string> = {
  aliyun: 'blue', openai: 'green', local: 'orange', vllm: 'purple',
};
const typeLabels: Record<string, string> = {
  generation: '生成模型', embedding: '嵌入模型', reranker: '重排模型', light: '轻量模型',
};

const ModelConfigList: React.FC = () => {
  const navigate = useNavigate();
  const [data] = useState([
    { id: '1', name: 'qwen-max-legal', display_name: '通义千问Max(法律版)', model_type: 'generation', provider: 'aliyun', model_id: 'qwen-max', temperature: 0.1, max_tokens: 8192, context_window: 32768, is_active: true, is_default: true, avg_latency_ms: 1500, quality_score: 4.2, error_rate: 0.003, created_at: '2024-01-15' },
    { id: '2', name: 'qwen-plus-preprocess', display_name: '通义千问Plus(预处理)', model_type: 'light', provider: 'aliyun', model_id: 'qwen-plus', temperature: 0.1, max_tokens: 4096, context_window: 32768, is_active: true, is_default: false, avg_latency_ms: 300, quality_score: 3.8, error_rate: 0.001, created_at: '2024-01-15' },
    { id: '3', name: 'text-embedding-v3', display_name: '通义嵌入V3', model_type: 'embedding', provider: 'aliyun', model_id: 'text-embedding-v3', temperature: 0, max_tokens: 0, context_window: 8192, is_active: true, is_default: true, avg_latency_ms: 50, quality_score: null, error_rate: 0.0005, created_at: '2024-01-15' },
    { id: '4', name: 'gte-rerank-legal', display_name: 'GTE重排(法律微调)', model_type: 'reranker', provider: 'aliyun', model_id: 'gte-rerank', temperature: 0, max_tokens: 0, context_window: 8192, is_active: true, is_default: true, avg_latency_ms: 120, quality_score: null, error_rate: 0.001, created_at: '2024-01-15' },
  ]);

  const columns = [
    {
      title: '模型名称', dataIndex: 'display_name', key: 'name',
      render: (text: string, record: any) => (
        <Space direction="vertical" size={0}>
          <a onClick={() => navigate(`/models/${record.id}`)}>{text}</a>
          <span style={{ fontSize: 12, color: '#999' }}>{record.model_id}</span>
        </Space>
      ),
    },
    {
      title: '类型', dataIndex: 'model_type', key: 'type',
      render: (t: string) => <Tag>{typeLabels[t] || t}</Tag>,
    },
    {
      title: '提供商', dataIndex: 'provider', key: 'provider',
      render: (p: string) => <Tag color={providerColors[p]}>{p.toUpperCase()}</Tag>,
    },
    {
      title: '参数', key: 'params',
      render: (_: any, r: any) => (
        <Space size={4} direction="vertical" style={{ fontSize: 12 }}>
          <span>温度: {r.temperature} | Top-K: {r.max_tokens}</span>
          <span>上下文: {(r.context_window / 1024).toFixed(0)}K</span>
        </Space>
      ),
    },
    {
      title: '性能', key: 'perf',
      render: (_: any, r: any) => (
        <Space size={4} direction="vertical" style={{ fontSize: 12 }}>
          <span>延迟: {r.avg_latency_ms}ms</span>
          <span>错误率: {((r.error_rate || 0) * 100).toFixed(2)}%</span>
        </Space>
      ),
    },
    {
      title: '状态', key: 'status',
      render: (_: any, r: any) => (
        <Space>
          <Badge status={r.is_active ? 'success' : 'default'} text={r.is_active ? '启用' : '停用'} />
          {r.is_default && <Tag color="gold">默认</Tag>}
        </Space>
      ),
    },
    {
      title: '操作', key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/models/${record.id}`)}>详情</Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => navigate(`/models/${record.id}/edit`)}>编辑</Button>
          <Popconfirm title="确认删除?" onConfirm={() => message.success('已删除')}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={4} style={{ margin: 0 }}>模型配置管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/models/create')}>新建模型配置</Button>
      </div>

      <Card size="small" className="mb-4">
        <Space>
          <Input placeholder="搜索模型名称" prefix={<SearchOutlined />} style={{ width: 200 }} />
          <Select placeholder="模型类型" allowClear style={{ width: 130 }}
            options={[
              { value: 'generation', label: '生成模型' },
              { value: 'embedding', label: '嵌入模型' },
              { value: 'reranker', label: '重排模型' },
              { value: 'light', label: '轻量模型' },
            ]}
          />
          <Select placeholder="提供商" allowClear style={{ width: 120 }}
            options={[
              { value: 'aliyun', label: '阿里云' },
              { value: 'openai', label: 'OpenAI' },
              { value: 'local', label: '本地部署' },
              { value: 'vllm', label: 'vLLM' },
            ]}
          />
        </Space>
      </Card>

      <Table dataSource={data} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} />
    </div>
  );
};

export default ModelConfigList;
