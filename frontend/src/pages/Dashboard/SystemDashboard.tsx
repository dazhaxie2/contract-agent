import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Card, Col, Row, Space, Statistic, Table, Typography } from 'antd';
import { Line } from '@ant-design/charts';

import { dashboardApi, SystemMetrics } from '../../services/api';

const { Title, Text } = Typography;

type Point = { timestamp: string; value: number };

function appendPoint(points: Point[], incoming: Point[], max = 60): Point[] {
  const next = [...points, ...incoming];
  if (next.length <= max) {
    return next;
  }
  return next.slice(next.length - max);
}

const SystemDashboard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [qpsHistory, setQpsHistory] = useState<Point[]>([]);
  const [latencyHistory, setLatencyHistory] = useState<Point[]>([]);
  const [errorRateHistory, setErrorRateHistory] = useState<Point[]>([]);

  const refresh = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await dashboardApi.getSystemMetrics();
      setMetrics(data);
      setQpsHistory((prev) => appendPoint(prev, data.qps));
      setLatencyHistory((prev) => appendPoint(prev, data.latency_p99));
      setErrorRateHistory((prev) => appendPoint(prev, data.error_rate));
    } catch (e) {
      setError('Failed to load system metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, []);

  const qpsCurrent = qpsHistory[qpsHistory.length - 1]?.value ?? 0;
  const p99Current = latencyHistory[latencyHistory.length - 1]?.value ?? 0;
  const errCurrent = errorRateHistory[errorRateHistory.length - 1]?.value ?? 0;
  const workbench = metrics?.contract_workbench;

  const services = metrics?.services ?? [];
  const serviceRows = useMemo(
    () =>
      services.map((svc) => ({
        name: svc.name,
        status: svc.status,
        uptime: `${Math.round((svc.uptime ?? 0) * 100)}%`,
        last_check: svc.last_check ?? '',
      })),
    [services],
  );

  return (
    <div>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Title level={4} style={{ margin: 0 }}>
            System Dashboard
          </Title>
          <Text type="secondary">{loading ? 'Refreshing...' : 'Auto refresh: 15s'}</Text>
        </Space>

        {error ? <Alert type="error" message={error} showIcon /> : null}

        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="Current QPS" value={qpsCurrent} precision={3} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="P99 Latency (ms)" value={p99Current} precision={2} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="5xx Error Rate" value={errCurrent * 100} precision={2} suffix="%" />
            </Card>
          </Col>
        </Row>

        <Card title="Contract Workbench Metrics" loading={loading && !metrics}>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="Plan Success" value={(workbench?.plan_success_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="Tool Failure" value={(workbench?.tool_failure_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="Citation Coverage" value={(workbench?.citation_coverage_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="Low Confidence" value={(workbench?.low_confidence_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="Feedback Avg" value={workbench?.user_feedback_avg || 0} precision={2} />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="Review Avg Latency" value={workbench?.contract_review_avg_latency_ms || 0} precision={0} suffix="ms" />
            </Col>
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card title="QPS Trend" loading={loading && qpsHistory.length === 0}>
              <Line
                data={qpsHistory.map((p) => ({ time: p.timestamp, value: p.value }))}
                xField="time"
                yField="value"
                smooth
                height={240}
                tooltip={{ showTitle: false }}
              />
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card title="P99 Latency Trend" loading={loading && latencyHistory.length === 0}>
              <Line
                data={latencyHistory.map((p) => ({ time: p.timestamp, value: p.value }))}
                xField="time"
                yField="value"
                smooth
                height={240}
                tooltip={{ showTitle: false }}
              />
            </Card>
          </Col>
        </Row>

        <Card title="Service Health" loading={loading && serviceRows.length === 0}>
          <Table
            rowKey="name"
            size="small"
            pagination={false}
            dataSource={serviceRows}
            columns={[
              { title: 'Service', dataIndex: 'name' },
              { title: 'Status', dataIndex: 'status' },
              { title: 'Uptime', dataIndex: 'uptime' },
              { title: 'Last Check', dataIndex: 'last_check' },
            ]}
          />
        </Card>
      </Space>
    </div>
  );
};

export default SystemDashboard;
