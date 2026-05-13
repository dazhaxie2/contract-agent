import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Card, Col, Row, Space, Statistic, Table, Typography } from 'antd';
import { Column } from '@ant-design/charts';

import { dashboardApi, RetrievalMetrics } from '../../services/api';

const { Title, Text } = Typography;

const RetrievalDashboard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [metrics, setMetrics] = useState<RetrievalMetrics | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await dashboardApi.getRetrievalMetrics();
      setMetrics(data);
    } catch {
      setError('Failed to load retrieval metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 20000);
    return () => window.clearInterval(timer);
  }, []);

  const channels = metrics?.channels ?? [];
  const channelRows = useMemo(
    () =>
      channels.map((item) => ({
        channel: item.name,
        top_k_hit_rate: item.top_k_hit_rate.join(', '),
        k_values: item.k_values.join(', '),
      })),
    [channels],
  );

  const recall = metrics?.recall_rate ?? 0;
  const precision = metrics?.precision_rate ?? 0;
  const before = metrics?.rerank_comparison?.before ?? 0;
  const after = metrics?.rerank_comparison?.after ?? 0;

  const chartData = [
    { metric: 'Recall@10', value: recall * 100 },
    { metric: 'Precision@10', value: precision * 100 },
    { metric: 'MRR Before', value: before * 100 },
    { metric: 'MRR After', value: after * 100 },
  ];

  return (
    <div>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Title level={4} style={{ margin: 0 }}>
            Retrieval Dashboard
          </Title>
          <Text type="secondary">{loading ? 'Refreshing...' : 'Auto refresh: 20s'}</Text>
        </Space>

        {error ? <Alert type="error" message={error} showIcon /> : null}

        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="Recall@10" value={recall * 100} precision={2} suffix="%" />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="Precision@10" value={precision * 100} precision={2} suffix="%" />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="MRR Before" value={before} precision={4} />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="MRR After" value={after} precision={4} />
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card title="Quality Metrics Comparison" loading={loading && !metrics}>
              <Column data={chartData} xField="metric" yField="value" height={260} />
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card title="Channel Contribution" loading={loading && !metrics}>
              <Table
                rowKey="channel"
                size="small"
                pagination={false}
                dataSource={channelRows}
                columns={[
                  { title: 'Channel', dataIndex: 'channel' },
                  { title: 'K', dataIndex: 'k_values' },
                  { title: 'Hit Rate', dataIndex: 'top_k_hit_rate' },
                ]}
              />
            </Card>
          </Col>
        </Row>
      </Space>
    </div>
  );
};

export default RetrievalDashboard;

