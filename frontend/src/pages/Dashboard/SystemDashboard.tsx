import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Statistic, Tag, Typography, Space, Table } from 'antd';
import {
  ArrowUpOutlined, ArrowDownOutlined,
  CheckCircleOutlined, WarningOutlined, CloseCircleOutlined,
  ThunderboltOutlined, ClockCircleOutlined, ApiOutlined,
} from '@ant-design/icons';
import { Line, Gauge } from '@ant-design/charts';

const { Title } = Typography;

const SystemDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState({
    qps: { current: 156, peak: 850, limit: 1000 },
    latency: { p50_ms: 120, p95_ms: 450, p99_ms: 980, avg_ms: 200 },
    error_rate: { rate_5xx: 0.002, rate_4xx: 0.015 },
    active_connections: 45,
  });

  // QPS时序数据
  const qpsData = Array.from({ length: 60 }, (_, i) => ({
    time: `${String(Math.floor(i / 60)).padStart(2, '0')}:${String(i % 60).padStart(2, '0')}`,
    value: 100 + Math.random() * 200,
    type: 'QPS',
  }));

  const latencyData = Array.from({ length: 60 }, (_, i) => ([
    { time: `${i}s`, value: 80 + Math.random() * 100, type: 'P50' },
    { time: `${i}s`, value: 200 + Math.random() * 400, type: 'P95' },
    { time: `${i}s`, value: 500 + Math.random() * 600, type: 'P99' },
  ])).flat();

  const services = [
    { name: 'FastAPI后端', status: 'healthy', replicas: '3/3', cpu: '35%', memory: '62%' },
    { name: 'PostgreSQL', status: 'healthy', replicas: '3/3', cpu: '20%', memory: '45%' },
    { name: 'Redis集群', status: 'healthy', replicas: '3/3', cpu: '15%', memory: '38%' },
    { name: 'Milvus向量库', status: 'healthy', replicas: '2/2', cpu: '40%', memory: '70%' },
    { name: 'NebulaGraph', status: 'healthy', replicas: '3/3', cpu: '25%', memory: '55%' },
    { name: 'Kafka集群', status: 'healthy', replicas: '3/3', cpu: '18%', memory: '42%' },
    { name: 'Jaeger追踪', status: 'healthy', replicas: '1/1', cpu: '10%', memory: '30%' },
  ];

  const statusColor = (s: string) =>
    s === 'healthy' ? 'success' : s === 'degraded' ? 'warning' : 'error';

  return (
    <div>
      <Title level={4}>系统监控总览</Title>

      {/* 核心指标卡片 */}
      <Row gutter={[16, 16]} className="mb-4">
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="当前QPS"
              value={metrics.qps.current}
              suffix={`/ ${metrics.qps.limit}`}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="平均延迟"
              value={metrics.latency.avg_ms}
              suffix="ms"
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="5xx错误率"
              value={(metrics.error_rate.rate_5xx * 100).toFixed(2)}
              suffix="%"
              prefix={<ArrowDownOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="活跃连接数"
              value={metrics.active_connections}
              prefix={<ApiOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* QPS & 延迟图表 */}
      <Row gutter={[16, 16]} className="mb-4">
        <Col xs={24} lg={12}>
          <Card title="QPS实时曲线" size="small">
            <Line
              data={qpsData}
              xField="time"
              yField="value"
              seriesField="type"
              smooth
              height={250}
              color={['#1677ff']}
              yAxis={{ label: { formatter: (v: string) => `${v}` } }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="延迟分布 (P50/P95/P99)" size="small">
            <Line
              data={latencyData}
              xField="time"
              yField="value"
              seriesField="type"
              smooth
              height={250}
              color={['#52c41a', '#faad14', '#f5222d']}
              yAxis={{ label: { formatter: (v: string) => `${v}ms` } }}
            />
          </Card>
        </Col>
      </Row>

      {/* QPS仪表盘 + 服务健康 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card title="QPS容量" size="small">
            <Gauge
              percent={metrics.qps.current / metrics.qps.limit}
              range={{ color: ['#1677ff', '#f0f0f0'] }}
              indicator={{ pointer: { style: { stroke: '#333' } } }}
              statistic={{
                content: {
                  formatter: () => `${metrics.qps.current} / ${metrics.qps.limit}`,
                  style: { fontSize: '18px' },
                },
              }}
              height={200}
            />
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card title="服务健康状态" size="small">
            <Table
              dataSource={services}
              rowKey="name"
              size="small"
              pagination={false}
              columns={[
                { title: '服务', dataIndex: 'name' },
                {
                  title: '状态', dataIndex: 'status',
                  render: (s: string) => <Tag color={statusColor(s)}>{s === 'healthy' ? '健康' : '异常'}</Tag>,
                },
                { title: '副本', dataIndex: 'replicas' },
                { title: 'CPU', dataIndex: 'cpu' },
                { title: '内存', dataIndex: 'memory' },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default SystemDashboard;
