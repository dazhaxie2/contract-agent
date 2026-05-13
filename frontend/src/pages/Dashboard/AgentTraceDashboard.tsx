import React, { useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Space,
  Statistic,
  Tag,
  Timeline,
  Typography,
} from 'antd';

import { dashboardApi, AgentTrace } from '../../services/api';

const { Title, Paragraph, Text } = Typography;

const AgentTraceDashboard: React.FC = () => {
  const [traceId, setTraceId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [trace, setTrace] = useState<AgentTrace | null>(null);

  const loadTrace = async () => {
    if (!traceId.trim()) {
      setError('Please input trace id');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await dashboardApi.getTrace(traceId.trim());
      setTrace(data);
    } catch {
      setTrace(null);
      setError('Trace not found or failed to load');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Title level={4} style={{ margin: 0 }}>
          Agent Trace Dashboard
        </Title>

        <Card>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="Input trace id"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
              onPressEnter={loadTrace}
            />
            <Button type="primary" loading={loading} onClick={loadTrace}>
              Search
            </Button>
          </Space.Compact>
        </Card>

        {error ? <Alert type="error" message={error} showIcon /> : null}

        {!trace ? (
          <Card>
            <Empty description="No trace loaded" />
          </Card>
        ) : (
          <>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic title="Total Duration (ms)" value={trace.total_duration_ms} precision={2} />
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic title="Total Tokens" value={trace.total_tokens} />
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic title="Steps" value={trace.steps.length} />
                </Card>
              </Col>
            </Row>

            <Row gutter={[16, 16]}>
              <Col xs={24} lg={14}>
                <Card title="Execution Timeline">
                  <Timeline
                    items={trace.steps.map((step) => ({
                      color: step.type === 'action' ? 'orange' : step.type === 'thought' ? 'blue' : 'green',
                      children: (
                        <div>
                          <Space size={8}>
                            <Tag>{step.type}</Tag>
                            <Text type="secondary">{step.duration_ms}ms</Text>
                            <Text type="secondary">{step.tokens} tokens</Text>
                          </Space>
                          <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>{step.content}</Paragraph>
                        </div>
                      ),
                    }))}
                  />
                </Card>
              </Col>
              <Col xs={24} lg={10}>
                <Card title="Trace Summary">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text>
                      Trace ID: <Text code>{trace.trace_id}</Text>
                    </Text>
                    <Text>
                      Status: <Tag>{trace.status}</Tag>
                    </Text>
                    <Text type="secondary">Created: {trace.created_at || '-'}</Text>
                  </Space>
                </Card>
              </Col>
            </Row>
          </>
        )}
      </Space>
    </div>
  );
};

export default AgentTraceDashboard;

