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
      setError('系统指标加载失败');
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
            系统总览
          </Title>
          <Text type="secondary">{loading ? '刷新中…' : '自动刷新：15 秒'}</Text>
        </Space>

        {error ? <Alert type="error" message={error} showIcon /> : null}

        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="当前 QPS" value={qpsCurrent} precision={3} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="P99 延迟 (ms)" value={p99Current} precision={2} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="5xx 错误率" value={errCurrent * 100} precision={2} suffix="%" />
            </Card>
          </Col>
        </Row>

        <Card title="合同工作台指标" loading={loading && !metrics}>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="规划成功率" value={(workbench?.plan_success_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="工具失败率" value={(workbench?.tool_failure_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="引用覆盖率" value={(workbench?.citation_coverage_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="低置信占比" value={(workbench?.low_confidence_rate || 0) * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="用户反馈均分" value={workbench?.user_feedback_avg || 0} precision={2} />
            </Col>
            <Col xs={12} md={8} xl={4}>
              <Statistic title="审查平均延迟" value={workbench?.contract_review_avg_latency_ms || 0} precision={0} suffix="ms" />
            </Col>
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card title="QPS 趋势" loading={loading && qpsHistory.length === 0}>
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
            <Card title="P99 延迟趋势" loading={loading && latencyHistory.length === 0}>
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

        <Card title="服务健康状况" loading={loading && serviceRows.length === 0}>
          <Table
            rowKey="name"
            size="small"
            pagination={false}
            dataSource={serviceRows}
            columns={[
              { title: '服务', dataIndex: 'name' },
              { title: '状态', dataIndex: 'status' },
              { title: '可用率', dataIndex: 'uptime' },
              { title: '最近检查', dataIndex: 'last_check' },
            ]}
          />
        </Card>
      </Space>
    </div>
  );
};

export default SystemDashboard;
