import React from 'react';
import { Card, Table, Tag, Button, Space, Typography, Progress, Row, Col, Statistic, Modal, Form, Select, Slider, Input } from 'antd';
import { ExperimentOutlined, PlayCircleOutlined, PauseOutlined } from '@ant-design/icons';
import { Column } from '@ant-design/charts';

const { Title } = Typography;

const ABTestPanel: React.FC = () => {
  const [showCreate, setShowCreate] = React.useState(false);

  const tests = [
    {
      id: '1', name: 'Qwen-Max vs Qwen-Plus 合同审查', test_type: 'model',
      status: 'running', traffic_split: 0.2,
      control: { name: 'Qwen-Max', quality: 4.2, latency: 1500, tokens: 850 },
      treatment: { name: 'Qwen-Plus', quality: 3.8, latency: 300, tokens: 650 },
      sample_count: 1250, started_at: '2024-01-20',
    },
    {
      id: '2', name: '提示词V3 vs V4 合规校验', test_type: 'prompt',
      status: 'completed', traffic_split: 0.3,
      control: { name: '提示词V3', quality: 3.9, latency: 1200, tokens: 780 },
      treatment: { name: '提示词V4', quality: 4.3, latency: 1100, tokens: 820 },
      sample_count: 5000, started_at: '2024-01-10',
    },
  ];

  const comparisonData = [
    { metric: '质量评分', group: 'Qwen-Max', value: 4.2 },
    { metric: '质量评分', group: 'Qwen-Plus', value: 3.8 },
    { metric: '延迟(s)', group: 'Qwen-Max', value: 1.5 },
    { metric: '延迟(s)', group: 'Qwen-Plus', value: 0.3 },
  ];

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={4} style={{ margin: 0 }}>A/B 测试管理</Title>
        <Button type="primary" icon={<ExperimentOutlined />} onClick={() => setShowCreate(true)}>创建A/B测试</Button>
      </div>

      {tests.map((test) => (
        <Card key={test.id} className="mb-4" title={
          <Space>
            <span>{test.name}</span>
            <Tag color={test.status === 'running' ? 'processing' : 'success'}>{test.status === 'running' ? '运行中' : '已完成'}</Tag>
            <Tag>{test.test_type === 'model' ? '模型对比' : '提示词对比'}</Tag>
          </Space>
        } extra={
          test.status === 'running' ? <Button danger icon={<PauseOutlined />}>停止</Button> : null
        }>
          <Row gutter={[16, 16]}>
            <Col span={4}><Statistic title="样本量" value={test.sample_count} /></Col>
            <Col span={4}><Statistic title="流量分配" value={`${(test.traffic_split * 100).toFixed(0)}%`} /></Col>
            <Col span={4}>
              <Statistic title={`${test.control.name} 质量`} value={test.control.quality} suffix="/5" valueStyle={{ color: '#1677ff' }} />
            </Col>
            <Col span={4}>
              <Statistic title={`${test.treatment.name} 质量`} value={test.treatment.quality} suffix="/5" valueStyle={{ color: '#52c41a' }} />
            </Col>
            <Col span={4}>
              <Statistic title={`${test.control.name} 延迟`} value={test.control.latency} suffix="ms" />
            </Col>
            <Col span={4}>
              <Statistic title={`${test.treatment.name} 延迟`} value={test.treatment.latency} suffix="ms" />
            </Col>
          </Row>
        </Card>
      ))}

      <Card title="指标对比图表" size="small">
        <Column
          data={comparisonData}
          xField="metric" yField="value" seriesField="group"
          isGroup height={300}
          color={['#1677ff', '#52c41a']}
          label={{ position: 'middle', style: { fill: '#fff' } }}
        />
      </Card>

      <Modal title="创建A/B测试" open={showCreate} onCancel={() => setShowCreate(false)} onOk={() => setShowCreate(false)}>
        <Form layout="vertical">
          <Form.Item label="测试名称"><Input placeholder="如: Qwen-Max vs GPT-4o 合同审查" /></Form.Item>
          <Form.Item label="测试类型">
            <Select options={[{ value: 'model', label: '模型对比' }, { value: 'prompt', label: '提示词对比' }, { value: 'retrieval', label: '检索策略对比' }]} />
          </Form.Item>
          <Form.Item label="流量分配"><Slider min={5} max={50} marks={{ 10: '10%', 20: '20%', 30: '30%', 50: '50%' }} /></Form.Item>
          <Form.Item label="主要评估指标">
            <Select options={[{ value: 'quality', label: '质量评分' }, { value: 'latency', label: '延迟' }, { value: 'recall', label: '召回率' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ABTestPanel;
