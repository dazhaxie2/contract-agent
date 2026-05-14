import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Card, Button, Tag, Space, Input, Select, Typography, Popconfirm, message, Badge } from 'antd';
import { PlusOutlined, SearchOutlined, EyeOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';

import { modelApi, ModelConfig } from '../../services/api';

const { Title } = Typography;

const providerColors: Record<string, string> = {
  aliyun: 'blue', openai: 'green', local: 'orange', vllm: 'purple',
};
const typeLabels: Record<string, string> = {
  generation: '生成模型', embedding: '嵌入模型', reranker: '重排模型', light: '轻量模型',
};

const ModelConfigList: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [modelType, setModelType] = useState<string>();
  const [provider, setProvider] = useState<string>();

  const loadModels = async () => {
    setLoading(true);
    try {
      const result = await modelApi.list({
        page: 1,
        page_size: 100,
        model_type: modelType,
        provider,
      });
      setData(result.items);
    } catch {
      message.error('模型配置加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadModels();
  }, [modelType, provider]);

  const filteredData = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return data;
    return data.filter((item) =>
      [item.name, item.display_name, item.model_id].some((value) => String(value || '').toLowerCase().includes(keyword)),
    );
  }, [data, search]);

  const deleteModel = async (id: string) => {
    try {
      await modelApi.delete(id);
      message.success('已删除');
      await loadModels();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '模型名称', dataIndex: 'display_name', key: 'name',
      render: (text: string, record: ModelConfig) => (
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
      render: (_: unknown, r: ModelConfig) => (
        <Space size={4} direction="vertical" style={{ fontSize: 12 }}>
          <span>温度: {r.temperature} | Top-K: {r.max_tokens}</span>
          <span>上下文: {(r.context_window / 1024).toFixed(0)}K</span>
        </Space>
      ),
    },
    {
      title: '性能', key: 'perf',
      render: (_: unknown, r: ModelConfig) => (
        <Space size={4} direction="vertical" style={{ fontSize: 12 }}>
          <span>延迟: {r.avg_latency_ms ?? '-'}ms</span>
          <span>错误率: {((r.error_rate || 0) * 100).toFixed(2)}%</span>
        </Space>
      ),
    },
    {
      title: '状态', key: 'status',
      render: (_: unknown, r: ModelConfig) => (
        <Space>
          <Badge status={r.is_active ? 'success' : 'default'} text={r.is_active ? '启用' : '停用'} />
          {r.is_default && <Tag color="gold">默认</Tag>}
        </Space>
      ),
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: ModelConfig) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/models/${record.id}`)}>详情</Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => navigate(`/models/${record.id}/edit`)}>编辑</Button>
          <Popconfirm title="确认删除?" onConfirm={() => deleteModel(record.id)}>
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
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索模型名称" prefix={<SearchOutlined />} style={{ width: 200 }} />
          <Select value={modelType} onChange={setModelType} placeholder="模型类型" allowClear style={{ width: 130 }}
            options={[
              { value: 'generation', label: '生成模型' },
              { value: 'embedding', label: '嵌入模型' },
              { value: 'reranker', label: '重排模型' },
              { value: 'light', label: '轻量模型' },
            ]}
          />
          <Select value={provider} onChange={setProvider} placeholder="提供商" allowClear style={{ width: 120 }}
            options={[
              { value: 'aliyun', label: '阿里云' },
              { value: 'openai', label: 'OpenAI' },
              { value: 'local', label: '本地部署' },
              { value: 'vllm', label: 'vLLM' },
            ]}
          />
        </Space>
      </Card>

      <Table loading={loading} dataSource={filteredData} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} />
    </div>
  );
};

export default ModelConfigList;
