import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Descriptions, Tag, Row, Col, Statistic, Button, Space, Typography, Badge } from 'antd';
import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import { Line } from '@ant-design/charts';

const { Title } = Typography;

const ModelConfigDetail: React.FC = () => {
  const navigate = useNavigate();

  const model = {
    id: '1', name: 'qwen-max-legal', display_name: '通义千问Max(法律版)',
    model_type: 'generation', provider: 'aliyun', model_id: 'qwen-max',
    temperature: 0.1, top_p: 0.8, max_tokens: 8192, context_window: 32768,
    is_active: true, is_default: true, version: 3,
    avg_latency_ms: 1500, avg_tokens_per_second: 45, error_rate: 0.003, quality_score: 4.2,
  };

  // 性能趋势数据
  const trendData = Array.from({ length: 24 }, (_, i) => ([
    { hour: `${i}:00`, value: 1200 + Math.random() * 600, metric: '延迟(ms)' },
    { hour: `${i}:00`, value: 30 + Math.random() * 30, metric: 'QPS' },
    { hour: `${i}:00`, value: Math.random() * 0.01, metric: '错误率' },
  ])).flat();

  return (
    <div>
      <Space className="mb-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/models')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>{model.display_name}</Title>
        <Badge status={model.is_active ? 'success' : 'default'} text={model.is_active ? '运行中' : '已停用'} />
        {model.is_default && <Tag color="gold">默认模型</Tag>}
      </Space>

      <Row gutter={[16, 16]} className="mb-4">
        <Col span={6}><Card><Statistic title="平均延迟" value={model.avg_latency_ms} suffix="ms" valueStyle={{ color: '#1677ff' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="吞吐量" value={model.avg_tokens_per_second} suffix="token/s" valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="错误率" value={(model.error_rate * 100).toFixed(2)} suffix="%" valueStyle={{ color: model.error_rate < 0.01 ? '#52c41a' : '#f5222d' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="质量评分" value={model.quality_score} suffix="/ 5" valueStyle={{ color: '#722ed1' }} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} className="mb-4">
        <Col span={12}>
          <Card title="模型配置详情" size="small" extra={<Button type="link" icon={<EditOutlined />} onClick={() => navigate(`/models/${model.id}/edit`)}>编辑</Button>}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="配置名称">{model.name}</Descriptions.Item>
              <Descriptions.Item label="模型ID">{model.model_id}</Descriptions.Item>
              <Descriptions.Item label="提供商"><Tag color="blue">{model.provider.toUpperCase()}</Tag></Descriptions.Item>
              <Descriptions.Item label="类型"><Tag>{model.model_type}</Tag></Descriptions.Item>
              <Descriptions.Item label="Temperature">{model.temperature}</Descriptions.Item>
              <Descriptions.Item label="Top-P">{model.top_p}</Descriptions.Item>
              <Descriptions.Item label="最大Token">{model.max_tokens}</Descriptions.Item>
              <Descriptions.Item label="上下文窗口">{(model.context_window / 1024).toFixed(0)}K</Descriptions.Item>
              <Descriptions.Item label="配置版本">v{model.version}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="性能趋势 (24小时)" size="small">
            <Line
              data={trendData.filter(d => d.metric === '延迟(ms)')}
              xField="hour" yField="value" seriesField="metric"
              height={220} smooth color={['#1677ff']}
              yAxis={{ label: { formatter: (v: string) => `${v}ms` } }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ModelConfigDetail;
