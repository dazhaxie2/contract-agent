import React, { useState } from 'react';
import { Card, Form, Input, Button, Select, Typography, Row, Col, Divider, Tag, Statistic, Space, Spin } from 'antd';
import { PlayCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const PromptTestPanel: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    output: string;
    model: string;
    latency_ms: number;
    tokens: { input: number; output: number; total: number };
  } | null>(null);

  const [variables, setVariables] = useState<Record<string, string>>({
    context: '依据《民法典》第五百七十七条：当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。',
    query: '甲方未按时交付货物，乙方可以追究什么样的违约责任？',
  });

  const handleTest = () => {
    setLoading(true);
    // 模拟调用
    setTimeout(() => {
      setResult({
        output: `## 违约责任分析

根据您提供的情况，甲方未按时交付货物构成**迟延履行**，乙方可主张以下违约责任：

### 1. 继续履行
依据《民法典》第五百七十七条，乙方有权要求甲方继续履行交付义务。

### 2. 违约金/赔偿损失
⚠️ **高风险提示**：若合同中约定了违约金条款，乙方可按约定主张违约金；若未约定或约定不足，可主张实际损失赔偿。

> 依据《民法典》第五百八十四条：当事人一方不履行合同义务或者履行合同义务不符合约定，造成对方损失的，损失赔偿额应当相当于因违约所造成的损失。

### 3. 解除合同
若迟延履行致使合同目的不能实现，乙方可依据《民法典》第五百六十三条主张解除合同。

**建议**：建议乙方首先发送书面催告函，给予合理期限要求甲方履行，逾期未履行再考虑解除合同并主张赔偿。`,
        model: 'qwen-max',
        latency_ms: 2340,
        tokens: { input: 580, output: 420, total: 1000 },
      });
      setLoading(false);
    }, 2000);
  };

  return (
    <div>
      <Title level={4}>提示词测试面板</Title>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="测试输入" size="small" className="mb-4">
            <Form.Item label="选择提示词模板">
              <Select placeholder="选择已有模板" style={{ width: '100%' }}
                options={[
                  { value: '1', label: '法律专家系统提示词 (v5)' },
                  { value: '2', label: '合同审查任务提示词 (v8)' },
                  { value: '3', label: '合规校验任务提示词 (v3)' },
                ]}
              />
            </Form.Item>

            <Form.Item label="选择模型">
              <Select defaultValue="qwen-max" style={{ width: '100%' }}
                options={[
                  { value: 'qwen-max', label: '通义千问Max (生成)' },
                  { value: 'qwen-plus', label: '通义千问Plus (轻量)' },
                ]}
              />
            </Form.Item>

            <Divider>变量赋值</Divider>

            <Form.Item label={<Space><Tag color="blue">{'{{context}}'}</Tag><Text type="secondary">检索上下文</Text></Space>}>
              <TextArea rows={4} value={variables.context}
                onChange={e => setVariables({ ...variables, context: e.target.value })}
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>

            <Form.Item label={<Space><Tag color="blue">{'{{query}}'}</Tag><Text type="secondary">用户查询</Text></Space>}>
              <TextArea rows={2} value={variables.query}
                onChange={e => setVariables({ ...variables, query: e.target.value })}
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>

            <Button type="primary" block icon={<PlayCircleOutlined />} onClick={handleTest} loading={loading} size="large">
              执行测试
            </Button>
          </Card>
        </Col>

        <Col span={12}>
          <Card title="测试结果" size="small">
            {loading ? (
              <div className="text-center py-20"><Spin size="large" tip="正在调用大模型..." /></div>
            ) : result ? (
              <>
                <Row gutter={16} className="mb-4">
                  <Col span={8}><Statistic title="延迟" value={result.latency_ms} suffix="ms" valueStyle={{ fontSize: 16 }} /></Col>
                  <Col span={8}><Statistic title="Token消耗" value={result.tokens.total} valueStyle={{ fontSize: 16 }} /></Col>
                  <Col span={8}><Statistic title="模型" value={result.model} valueStyle={{ fontSize: 14 }} /></Col>
                </Row>
                <Divider />
                <div className="p-4 bg-gray-50 rounded" style={{ maxHeight: 500, overflow: 'auto', whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                  {result.output}
                </div>
              </>
            ) : (
              <div className="text-center py-20">
                <ThunderboltOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                <div className="mt-4"><Text type="secondary">点击"执行测试"查看输出结果</Text></div>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PromptTestPanel;
