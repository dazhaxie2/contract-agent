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
      setError('请输入链路 ID');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await dashboardApi.getTrace(traceId.trim());
      setTrace(data);
    } catch {
      setTrace(null);
      setError('未找到链路，或加载失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Title level={4} style={{ margin: 0 }}>
          链路追踪
        </Title>

        <Card>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="请输入链路 ID"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
              onPressEnter={loadTrace}
            />
            <Button type="primary" loading={loading} onClick={loadTrace}>
              查询
            </Button>
          </Space.Compact>
        </Card>

        {error ? <Alert type="error" message={error} showIcon /> : null}

        {!trace ? (
          <Card>
            <Empty description="暂无链路数据" />
          </Card>
        ) : (
          <>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic title="总耗时 (ms)" value={trace.total_duration_ms} precision={2} />
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic title="总 Token 数" value={trace.total_tokens} />
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic title="步骤数" value={trace.steps.length} />
                </Card>
              </Col>
            </Row>

            <Row gutter={[16, 16]}>
              <Col xs={24} lg={14}>
                <Card title="执行时间线">
                  <Timeline
                    items={trace.steps.map((step) => ({
                      color: step.type === 'action' ? 'orange' : step.type === 'thought' ? 'blue' : 'green',
                      children: (
                        <div>
                          <Space size={8}>
                            <Tag>{step.type}</Tag>
                            <Text type="secondary">{step.duration_ms} ms</Text>
                            <Text type="secondary">{step.tokens} Token</Text>
                          </Space>
                          <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>{step.content}</Paragraph>
                        </div>
                      ),
                    }))}
                  />
                </Card>
              </Col>
              <Col xs={24} lg={10}>
                <Card title="链路摘要">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text>
                      链路 ID：<Text code>{trace.trace_id}</Text>
                    </Text>
                    <Text>
                      状态：<Tag>{trace.status}</Tag>
                    </Text>
                    <Text type="secondary">创建时间：{trace.created_at || '-'}</Text>
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

