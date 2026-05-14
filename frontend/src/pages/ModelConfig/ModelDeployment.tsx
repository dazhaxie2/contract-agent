import React, { useEffect, useState } from 'react';
import { Badge, Button, Card, Empty, Progress, Space, Table, Tag, Typography, message } from 'antd';
import { PauseCircleOutlined, ReloadOutlined, RocketOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { DeploymentInfo, modelApi } from '../../services/api';

const { Title } = Typography;

const statusMap: Record<string, { color: 'success' | 'default' | 'processing' | 'error' | 'warning'; text: string }> = {
  pending: { color: 'warning', text: '待部署' },
  running: { color: 'success', text: '运行中' },
  stopped: { color: 'default', text: '已停止' },
  deploying: { color: 'processing', text: '部署中' },
  failed: { color: 'error', text: '失败' },
  unknown: { color: 'default', text: '未知' },
};

const deploymentTypeLabels: Record<string, string> = {
  cloud_api: '云 API',
  vllm: 'vLLM',
  triton: 'Triton',
  onnx: 'ONNX',
};

const ModelDeployment: React.FC = () => {
  const navigate = useNavigate();
  const [deployments, setDeployments] = useState<DeploymentInfo[]>([]);
  const [loading, setLoading] = useState(false);

  const loadDeployments = async () => {
    setLoading(true);
    try {
      setDeployments(await modelApi.getDeployments());
    } catch {
      message.error('部署列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDeployments();
  }, []);

  const stopDeployment = async (deployment: DeploymentInfo) => {
    try {
      await modelApi.undeploy(deployment.model_id);
      message.success('已停止部署');
      await loadDeployments();
    } catch {
      message.error('停止部署失败');
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>
          模型部署管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadDeployments} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<RocketOutlined />} onClick={() => navigate('/models')}>
            选择模型部署
          </Button>
        </Space>
      </Space>

      <Card>
        <Table
          loading={loading}
          dataSource={deployments}
          rowKey="id"
          locale={{ emptyText: <Empty description="暂无部署记录" /> }}
          columns={[
            { title: '模型名称', dataIndex: 'model_name' },
            {
              title: '部署类型',
              render: (_: unknown, row: DeploymentInfo) => (
                <Tag>{deploymentTypeLabels[row.deployment_type] || row.deployment_type}</Tag>
              ),
            },
            {
              title: '状态',
              dataIndex: 'status',
              render: (status: string) => (
                <Badge status={statusMap[status]?.color || 'default'} text={statusMap[status]?.text || status} />
              ),
            },
            {
              title: 'GPU',
              render: (_: unknown, row: DeploymentInfo) =>
                row.gpu_count > 0 ? `${row.gpu_type} x ${row.gpu_count}` : '-',
            },
            {
              title: '副本',
              render: (_: unknown, row: DeploymentInfo) => `${row.ready_replicas} / ${row.replicas}`,
            },
            {
              title: 'QPS',
              render: (_: unknown, row: DeploymentInfo) => {
                const percent = row.max_qps > 0 ? Math.round((row.current_qps / row.max_qps) * 100) : 0;
                return (
                  <Space direction="vertical" size={0}>
                    <span>{row.max_qps > 0 ? `${row.current_qps} / ${row.max_qps}` : '-'}</span>
                    <Progress percent={percent} size="small" showInfo={false} />
                  </Space>
                );
              },
            },
            {
              title: '延迟',
              render: (_: unknown, row: DeploymentInfo) =>
                row.avg_latency_ms || row.p99_latency_ms
                  ? `Avg ${row.avg_latency_ms}ms / P99 ${row.p99_latency_ms}ms`
                  : '-',
            },
            {
              title: '资源',
              render: (_: unknown, row: DeploymentInfo) =>
                row.cpu_usage === null && row.memory_usage === null
                  ? '未接入监控'
                  : `CPU ${row.cpu_usage ?? '-'}% / MEM ${row.memory_usage ?? '-'}%`,
            },
            {
              title: '操作',
              render: (_: unknown, row: DeploymentInfo) => (
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<PauseCircleOutlined />}
                  onClick={() => stopDeployment(row)}
                >
                  停止
                </Button>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
};

export default ModelDeployment;
