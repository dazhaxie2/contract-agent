import React, { useEffect, useState } from 'react';
import { Alert, Button, Col, Input, Row, Select, Space, Statistic, Typography, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';

import { promptApi, PromptTemplate, PromptTestResult } from '../../services/api';

const { Title, Text } = Typography;
const { TextArea } = Input;

const PromptTestPanel: React.FC = () => {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [templateId, setTemplateId] = useState('');
  const [variablesJson, setVariablesJson] = useState('{\n  "content": "请审查合同中的付款、违约和解除条款。"\n}');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<PromptTestResult | null>(null);

  useEffect(() => {
    promptApi
      .list({ page: 1, page_size: 100 })
      .then((data) => {
        setTemplates(data.items);
        if (data.items[0]) setTemplateId(data.items[0].id);
      })
      .catch(() => undefined);
  }, []);

  const handleTest = async () => {
    if (!templateId) {
      message.warning('请选择提示词模板');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const variables = JSON.parse(variablesJson) as Record<string, unknown>;
      setResult(await promptApi.test(templateId, variables));
    } catch (e) {
      const msg = e instanceof SyntaxError ? '变量必须是合法 JSON' : '提示词测试失败';
      setError(msg);
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Title level={4} style={{ margin: 0 }}>
          提示词测试
        </Title>
        <Text type="secondary">选择模板并使用真实模型链路测试输出</Text>
      </div>

      {error ? <Alert type="error" message={error} showIcon /> : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <div className="panel-block">
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Select
                placeholder="选择提示词模板"
                value={templateId || undefined}
                onChange={setTemplateId}
                options={templates.map((item) => ({
                  value: item.id,
                  label: `${item.display_name || item.name} v${item.current_version}`,
                }))}
              />
              <TextArea
                rows={12}
                value={variablesJson}
                onChange={(event) => setVariablesJson(event.target.value)}
                className="code-editor"
              />
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleTest} loading={loading}>
                执行测试
              </Button>
            </Space>
          </div>
        </Col>
        <Col xs={24} lg={14}>
          <div className="panel-block">
            {result ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic title="延迟" value={result.latency_ms} suffix="ms" />
                  </Col>
                  <Col span={8}>
                    <Statistic title="Token" value={result.tokens_used} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="评分" value={result.score} precision={2} />
                  </Col>
                </Row>
                <pre className="result-markdown">{result.output}</pre>
                <Text type="secondary">模型：{result.model_used || '-'}</Text>
              </Space>
            ) : (
              <Alert type="info" message="执行测试后将在这里展示模型输出" showIcon />
            )}
          </div>
        </Col>
      </Row>
    </Space>
  );
};

export default PromptTestPanel;
