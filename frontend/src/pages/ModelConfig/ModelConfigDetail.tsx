import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Alert, Badge, Button, Card, Col, Descriptions, Empty, Row, Space, Statistic, Tag, Typography } from 'antd';
import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';

import { SimpleLineChart } from '../../components/Charts/SimpleCharts';
import { modelApi, ModelConfig, ModelMetrics } from '../../services/api';

const { Title } = Typography;

const providerColors: Record<string, string> = {
  aliyun: 'blue',
  openai: 'green',
  local: 'orange',
  vllm: 'purple',
};

const ModelConfigDetail: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError('');
    Promise.all([modelApi.get(id), modelApi.getMetrics(id, '24h')])
      .then(([modelData, metricData]) => {
        setModel(modelData);
        setMetrics(metricData);
      })
      .catch(() => setError('模型详情加载失败'))
      .finally(() => setLoading(false));
  }, [id]);

  const trendData = useMemo(
    () =>
      (metrics?.timestamps || []).map((time, index) => ({
        time,
        value: metrics?.latency_p99?.[index] || 0,
      })),
    [metrics],
  );

  if (!loading && !model) {
    return (
      <Card>
        {error ? <Alert type="error" message={error} showIcon /> : <Empty description="模型不存在" />}
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {error ? <Alert type="error" message={error} showIcon /> : null}
      <Space className="mb-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/models')}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          {model?.display_name || '模型详情'}
        </Title>
        <Badge status={model?.is_active ? 'success' : 'default'} text={model?.is_active ? '启用' : '停用'} />
        {model?.is_default ? <Tag color="gold">默认模型</Tag> : null}
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={6}>
          <Card loading={loading}>
            <Statistic title="平均延迟" value={model?.avg_latency_ms ?? 0} suffix="ms" />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card loading={loading}>
            <Statistic title="吞吐量" value={model?.avg_tokens_per_second ?? 0} suffix="token/s" />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card loading={loading}>
            <Statistic title="错误率" value={(model?.error_rate ?? 0) * 100} precision={2} suffix="%" />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card loading={loading}>
            <Statistic title="质量评分" value={model?.quality_score ?? 0} precision={2} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title="模型配置详情"
            loading={loading}
            size="small"
            extra={
              model ? (
                <Button type="link" icon={<EditOutlined />} onClick={() => navigate(`/models/${model.id}/edit`)}>
                  编辑
                </Button>
              ) : null
            }
          >
            {model ? (
              <Descriptions column={2} size="small">
                <Descriptions.Item label="配置名称">{model.name}</Descriptions.Item>
                <Descriptions.Item label="模型 ID">{model.model_id}</Descriptions.Item>
                <Descriptions.Item label="提供商">
                  <Tag color={providerColors[model.provider]}>{model.provider.toUpperCase()}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="类型">
                  <Tag>{model.model_type}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Temperature">{model.temperature}</Descriptions.Item>
                <Descriptions.Item label="Top-P">{model.top_p}</Descriptions.Item>
                <Descriptions.Item label="最大 Token">{model.max_tokens}</Descriptions.Item>
                <Descriptions.Item label="上下文窗口">{model.context_window}</Descriptions.Item>
                <Descriptions.Item label="配置版本">v{model.version || 1}</Descriptions.Item>
              </Descriptions>
            ) : null}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="性能趋势 (24小时)" size="small" loading={loading}>
            {trendData.length ? (
              <SimpleLineChart data={trendData.map((item) => ({ label: item.time, value: item.value }))} height={220} />
            ) : (
              <Empty description="暂无执行样本" />
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  );
};

export default ModelConfigDetail;
