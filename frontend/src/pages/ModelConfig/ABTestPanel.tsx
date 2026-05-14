import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Empty, Form, Input, Modal, Row, Select, Slider, Space, Statistic, Table, Tag, Typography, message } from 'antd';
import { ExperimentOutlined, PauseOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { Column } from '@ant-design/charts';

import { ABTest, ModelConfig, modelApi } from '../../services/api';

const { Title, Text } = Typography;

function metric(metrics: Record<string, unknown> | undefined, key: string) {
  return Number(metrics?.[key] || 0);
}

const ABTestPanel: React.FC = () => {
  const [form] = Form.useForm();
  const [showCreate, setShowCreate] = useState(false);
  const [tests, setTests] = useState<ABTest[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(false);

  const modelName = (id?: string) =>
    models.find((item) => item.id === id)?.display_name || models.find((item) => item.id === id)?.name || id?.slice(0, 8) || '-';

  const load = async () => {
    setLoading(true);
    try {
      const [abTests, modelPage] = await Promise.all([
        modelApi.listABTests(),
        modelApi.list({ page: 1, page_size: 100 }),
      ]);
      setTests(abTests);
      setModels(modelPage.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  const comparisonData = useMemo(
    () =>
      tests.flatMap((test) => [
        {
          test: test.name,
          metric: '质量评分',
          group: modelName(test.control_config_id),
          value: metric(test.control_metrics, 'quality_score'),
        },
        {
          test: test.name,
          metric: '质量评分',
          group: modelName(test.treatment_config_id),
          value: metric(test.treatment_metrics, 'quality_score'),
        },
        {
          test: test.name,
          metric: '延迟(ms)',
          group: modelName(test.control_config_id),
          value: metric(test.control_metrics, 'latency_ms'),
        },
        {
          test: test.name,
          metric: '延迟(ms)',
          group: modelName(test.treatment_config_id),
          value: metric(test.treatment_metrics, 'latency_ms'),
        },
      ]),
    [tests, models],
  );

  const createTest = async () => {
    const values = await form.validateFields();
    await modelApi.createABTest(values);
    message.success('A/B 测试已创建');
    setShowCreate(false);
    form.resetFields();
    await load();
  };

  const changeStatus = async (test: ABTest, action: 'start' | 'stop') => {
    if (action === 'start') {
      await modelApi.startABTest(test.id);
      message.success('A/B 测试已启动');
    } else {
      await modelApi.stopABTest(test.id);
      message.success('A/B 测试已停止');
    }
    await load();
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            A/B 测试管理
          </Title>
          <Text type="secondary">模型、提示词、检索策略的真实实验记录和效果对比</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={() => setShowCreate(true)}>
            创建 A/B 测试
          </Button>
        </Space>
      </Space>

      {tests.length ? (
        tests.map((test) => (
          <Card
            key={test.id}
            title={
              <Space wrap>
                <span>{test.name}</span>
                <Tag color={test.status === 'running' ? 'processing' : test.status === 'completed' ? 'success' : 'default'}>
                  {test.status}
                </Tag>
                <Tag>{test.test_type || 'model'}</Tag>
                {test.winner ? <Tag color="green">winner: {test.winner}</Tag> : null}
              </Space>
            }
            extra={
              test.status === 'running' ? (
                <Button danger icon={<PauseOutlined />} onClick={() => changeStatus(test, 'stop')}>
                  停止
                </Button>
              ) : (
                <Button icon={<PlayCircleOutlined />} onClick={() => changeStatus(test, 'start')}>
                  启动
                </Button>
              )
            }
          >
            <Row gutter={[16, 16]}>
              <Col xs={12} md={4}>
                <Statistic title="流量分配" value={(test.traffic_split || 0) * 100} precision={0} suffix="%" />
              </Col>
              <Col xs={12} md={4}>
                <Statistic title="主指标" value={test.primary_metric || '-'} />
              </Col>
              <Col xs={12} md={4}>
                <Statistic title={`${modelName(test.control_config_id)} 质量`} value={metric(test.control_metrics, 'quality_score')} precision={2} />
              </Col>
              <Col xs={12} md={4}>
                <Statistic title={`${modelName(test.treatment_config_id)} 质量`} value={metric(test.treatment_metrics, 'quality_score')} precision={2} />
              </Col>
              <Col xs={12} md={4}>
                <Statistic title="控制组延迟" value={metric(test.control_metrics, 'latency_ms')} suffix="ms" />
              </Col>
              <Col xs={12} md={4}>
                <Statistic title="实验组延迟" value={metric(test.treatment_metrics, 'latency_ms')} suffix="ms" />
              </Col>
            </Row>
          </Card>
        ))
      ) : (
        <Card loading={loading}>
          <Empty description="暂无 A/B 测试" />
        </Card>
      )}

      <Card title="效果对比" size="small">
        <Column
          data={comparisonData}
          xField="metric"
          yField="value"
          seriesField="group"
          isGroup
          height={300}
          label={{ position: 'middle', style: { fill: '#fff' } }}
        />
      </Card>

      <Card title="Prompt 版本效果对比" size="small">
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={tests.filter((item) => item.test_type === 'prompt')}
          columns={[
            { title: '测试', dataIndex: 'name' },
            { title: '控制组', render: (_, row) => modelName(row.control_config_id) },
            { title: '实验组', render: (_, row) => modelName(row.treatment_config_id) },
            { title: '控制组质量', render: (_, row) => metric(row.control_metrics, 'quality_score') },
            { title: '实验组质量', render: (_, row) => metric(row.treatment_metrics, 'quality_score') },
            { title: '状态', dataIndex: 'status' },
          ]}
        />
      </Card>

      <Modal title="创建 A/B 测试" open={showCreate} onCancel={() => setShowCreate(false)} onOk={createTest}>
        <Form form={form} layout="vertical" initialValues={{ test_type: 'model', traffic_split: 0.1, primary_metric: 'quality_score' }}>
          <Form.Item name="name" label="测试名称" rules={[{ required: true }]}>
            <Input placeholder="如：Qwen-Max vs Qwen-Plus 合同审查" />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input />
          </Form.Item>
          <Form.Item name="test_type" label="测试类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'model', label: '模型对比' }, { value: 'prompt', label: '提示词对比' }, { value: 'retrieval', label: '检索策略对比' }, { value: 'rerank', label: '重排策略对比' }]} />
          </Form.Item>
          <Form.Item name="control_config_id" label="控制组" rules={[{ required: true }]}>
            <Select options={models.map((item) => ({ value: item.id, label: item.display_name || item.name }))} />
          </Form.Item>
          <Form.Item name="treatment_config_id" label="实验组" rules={[{ required: true }]}>
            <Select options={models.map((item) => ({ value: item.id, label: item.display_name || item.name }))} />
          </Form.Item>
          <Form.Item name="traffic_split" label="流量分配">
            <Slider min={0.01} max={0.5} step={0.01} marks={{ 0.1: '10%', 0.3: '30%', 0.5: '50%' }} />
          </Form.Item>
          <Form.Item name="primary_metric" label="主要评估指标" rules={[{ required: true }]}>
            <Select options={[{ value: 'quality_score', label: '质量评分' }, { value: 'latency_ms', label: '延迟' }, { value: 'citation_coverage', label: '引用覆盖率' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};

export default ABTestPanel;
