import React from 'react';
import { Card, Table, Tag, Button, Space, Typography, Progress, Badge } from 'antd';
import { RocketOutlined, PauseCircleOutlined, ReloadOutlined } from '@ant-design/icons';

const { Title } = Typography;

const ModelDeployment: React.FC = () => {
  const deployments = [
    { id: '1', model_name: '通义千问Max', deployment_type: 'cloud_api', status: 'running', gpu_type: '-', gpu_count: 0, replicas: 3, endpoint: 'https://dashscope.aliyuncs.com', current_qps: 45.2, max_qps: 100, avg_latency_ms: 1500, p99_latency_ms: 5200, health: 'healthy' },
    { id: '2', model_name: '通义千问Plus', deployment_type: 'cloud_api', status: 'running', gpu_type: '-', gpu_count: 0, replicas: 5, endpoint: 'https://dashscope.aliyuncs.com', current_qps: 120.5, max_qps: 300, avg_latency_ms: 300, p99_latency_ms: 800, health: 'healthy' },
    { id: '3', model_name: 'BGE-Reranker-Large', deployment_type: 'vllm', status: 'running', gpu_type: 'A100', gpu_count: 2, replicas: 2, endpoint: 'http://reranker:8080', current_qps: 200, max_qps: 500, avg_latency_ms: 120, p99_latency_ms: 300, health: 'healthy' },
    { id: '4', model_name: 'BGE-Large-zh (嵌入)', deployment_type: 'onnx', status: 'running', gpu_type: 'T4', gpu_count: 4, replicas: 4, endpoint: 'http://embedding:8080', current_qps: 800, max_qps: 1200, avg_latency_ms: 50, p99_latency_ms: 100, health: 'healthy' },
  ];

  const statusMap: Record<string, { color: string; text: string }> = {
    running: { color: 'success', text: '运行中' },
    stopped: { color: 'default', text: '已停止' },
    deploying: { color: 'processing', text: '部署中' },
    failed: { color: 'error', text: '失败' },
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={4} style={{ margin: 0 }}>模型部署管理</Title>
        <Button type="primary" icon={<RocketOutlined />}>新建部署</Button>
      </div>

      <Table
        dataSource={deployments}
        rowKey="id"
        columns={[
          { title: '模型名称', dataIndex: 'model_name' },
          { title: '部署类型', dataIndex: 'deployment_type', render: (t: string) => <Tag>{t.toUpperCase()}</Tag> },
          {
            title: '状态', dataIndex: 'status',
            render: (s: string) => <Badge status={statusMap[s]?.color as any} text={statusMap[s]?.text} />,
          },
          {
            title: 'GPU', key: 'gpu',
            render: (_, r: any) => r.gpu_count > 0 ? `${r.gpu_type} x ${r.gpu_count}` : '-',
          },
          { title: '副本数', dataIndex: 'replicas' },
          {
            title: 'QPS', key: 'qps',
            render: (_, r: any) => (
              <Space direction="vertical" size={0}>
                <span>{r.current_qps} / {r.max_qps}</span>
                <Progress percent={Math.round(r.current_qps / r.max_qps * 100)} size="small" showInfo={false} />
              </Space>
            ),
          },
          {
            title: '延迟', key: 'latency',
            render: (_, r: any) => <span>P50: {r.avg_latency_ms}ms | P99: {r.p99_latency_ms}ms</span>,
          },
          {
            title: '操作', key: 'action',
            render: () => (
              <Space>
                <Button type="link" size="small" icon={<ReloadOutlined />}>扩容</Button>
                <Button type="link" size="small" danger icon={<PauseCircleOutlined />}>停止</Button>
              </Space>
            ),
          },
        ]}
      />
    </div>
  );
};

export default ModelDeployment;
