import React, { useState } from 'react';
import { Card, Input, Button, Timeline, Tag, Typography, Descriptions, Row, Col, Statistic, Empty, Space } from 'antd';
import { SearchOutlined, ClockCircleOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

interface TraceStep {
  step_number: number;
  step_type: string;
  content: string;
  action?: string;
  tool_name?: string;
  tokens_used: number;
  latency_ms: number;
}

const AgentTraceDashboard: React.FC = () => {
  const [traceId, setTraceId] = useState('');
  const [traceData, setTraceData] = useState<{
    trace_id: string;
    status: string;
    result: string;
    steps: TraceStep[];
    usage: { total_tokens: number; retrieval_chunks: number };
    latency_ms: number;
    references: { ref_id: number; source: string; hierarchy: string; score: number }[];
  } | null>(null);

  const handleSearch = () => {
    // 模拟数据
    setTraceData({
      trace_id: traceId || 'a1b2c3d4e5f6',
      status: 'completed',
      result: '根据《民法典》第五百七十七条，当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任...',
      steps: [
        { step_number: 1, step_type: 'thought', content: '用户询问合同违约责任条款，需要检索相关法律法规', tokens_used: 150, latency_ms: 200 },
        { step_number: 2, step_type: 'action', content: '调用知识库检索', action: 'search_knowledge_base', tool_name: 'search_knowledge_base', tokens_used: 0, latency_ms: 350 },
        { step_number: 3, step_type: 'observation', content: '检索到5条相关法条: 民法典第577条、第584条...', tokens_used: 0, latency_ms: 0 },
        { step_number: 4, step_type: 'action', content: '合规性校验', action: 'compliance_check', tool_name: 'compliance_check', tokens_used: 200, latency_ms: 1500 },
        { step_number: 5, step_type: 'observation', content: '合规检查通过，未发现风险点', tokens_used: 0, latency_ms: 0 },
        { step_number: 6, step_type: 'final', content: '生成最终回复', tokens_used: 800, latency_ms: 2500 },
      ],
      usage: { total_tokens: 1150, retrieval_chunks: 5 },
      latency_ms: 4550,
      references: [
        { ref_id: 1, source: '《民法典》第577条', hierarchy: '第三编 > 第八章', score: 0.96 },
        { ref_id: 2, source: '《民法典》第584条', hierarchy: '第三编 > 第八章', score: 0.92 },
        { ref_id: 3, source: '《合同法司法解释二》第29条', hierarchy: '赔偿', score: 0.85 },
      ],
    });
  };

  const stepColor = (type: string) => {
    switch (type) {
      case 'thought': return 'blue';
      case 'action': return 'orange';
      case 'observation': return 'green';
      case 'validation': return 'purple';
      case 'final': return 'cyan';
      default: return 'gray';
    }
  };

  const stepLabel = (type: string) => {
    switch (type) {
      case 'thought': return '思考';
      case 'action': return '行动';
      case 'observation': return '观察';
      case 'validation': return '校验';
      case 'final': return '输出';
      default: return type;
    }
  };

  return (
    <div>
      <Title level={4}>Agent链路追踪</Title>

      <Card className="mb-4">
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="输入 Trace ID 查询执行链路"
            value={traceId}
            onChange={(e) => setTraceId(e.target.value)}
            onPressEnter={handleSearch}
            prefix={<SearchOutlined />}
            size="large"
          />
          <Button type="primary" size="large" onClick={handleSearch}>查询</Button>
        </Space.Compact>
      </Card>

      {traceData ? (
        <>
          {/* 执行概览 */}
          <Row gutter={[16, 16]} className="mb-4">
            <Col span={6}>
              <Card><Statistic title="总耗时" value={traceData.latency_ms} suffix="ms" valueStyle={{ color: '#1677ff' }} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="总Token" value={traceData.usage.total_tokens} valueStyle={{ color: '#722ed1' }} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="执行步骤" value={traceData.steps.length} valueStyle={{ color: '#52c41a' }} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="检索块数" value={traceData.usage.retrieval_chunks} valueStyle={{ color: '#faad14' }} /></Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            {/* ReAct执行链路 */}
            <Col span={14}>
              <Card title="ReAct 执行流程" size="small">
                <Timeline
                  items={traceData.steps.map((step) => ({
                    color: stepColor(step.step_type),
                    children: (
                      <div className="pb-2">
                        <Space className="mb-1">
                          <Tag color={stepColor(step.step_type)}>{stepLabel(step.step_type)}</Tag>
                          {step.tool_name && <Tag color="geekblue">{step.tool_name}</Tag>}
                          <Text type="secondary">{step.latency_ms}ms</Text>
                          {step.tokens_used > 0 && <Text type="secondary">{step.tokens_used} tokens</Text>}
                        </Space>
                        <Paragraph ellipsis={{ rows: 2, expandable: true }} style={{ marginBottom: 0 }}>
                          {step.content}
                        </Paragraph>
                      </div>
                    ),
                  }))}
                />
              </Card>
            </Col>

            {/* 引用来源 */}
            <Col span={10}>
              <Card title="引用来源" size="small" className="mb-4">
                {traceData.references.map((ref) => (
                  <div key={ref.ref_id} className="p-2 mb-2 bg-gray-50 rounded">
                    <Space>
                      <Tag color="blue">[参考{ref.ref_id}]</Tag>
                      <Text strong>{ref.source}</Text>
                    </Space>
                    <div><Text type="secondary">{ref.hierarchy} | 相关度: {(ref.score * 100).toFixed(1)}%</Text></div>
                  </div>
                ))}
              </Card>

              <Card title="生成结果" size="small">
                <Tag color={traceData.status === 'completed' ? 'success' : 'error'} className="mb-2">
                  {traceData.status === 'completed' ? '成功' : '失败'}
                </Tag>
                <Paragraph>{traceData.result}</Paragraph>
              </Card>
            </Col>
          </Row>
        </>
      ) : (
        <Card><Empty description="输入 Trace ID 查看Agent执行链路" /></Card>
      )}
    </div>
  );
};

export default AgentTraceDashboard;
