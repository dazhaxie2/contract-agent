import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, Select, Button, Space, Typography, Row, Col, Tag, Table, Tabs, Switch, Divider, message } from 'antd';
import { SaveOutlined, ArrowLeftOutlined, PlusOutlined, DeleteOutlined, EyeOutlined, PlayCircleOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface Variable {
  name: string;
  type: string;
  description: string;
  default_value: string;
  required: boolean;
}

const PromptEditor: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [variables, setVariables] = useState<Variable[]>([
    { name: 'context', type: 'string', description: '检索上下文', default_value: '', required: true },
    { name: 'query', type: 'string', description: '用户查询', default_value: '', required: true },
  ]);
  const [systemPrompt, setSystemPrompt] = useState(
    '你是一位资深合同合规法律专家。\n\n## 核心规则\n1. 所有内容必须基于检索上下文，禁止编造\n2. 必须标注引用来源\n3. 不确定的内容必须声明'
  );
  const [userTemplate, setUserTemplate] = useState(
    '## 检索上下文\n{{context}}\n\n## 用户问题\n{{query}}\n\n请基于以上检索上下文回答用户问题，要求：\n1. 引用具体法条\n2. 标注风险点\n3. 给出修改建议'
  );
  const [previewMode, setPreviewMode] = useState(false);

  // 变量高亮渲染
  const highlightedTemplate = useMemo(() => {
    let text = userTemplate;
    variables.forEach(v => {
      const pattern = `{{${v.name}}}`;
      text = text.replaceAll(pattern, `<span class="bg-blue-100 text-blue-700 px-1 rounded font-mono">\{\{${v.name}\}\}</span>`);
    });
    return text;
  }, [userTemplate, variables]);

  // 预览（替换变量为默认值）
  const previewText = useMemo(() => {
    let text = userTemplate;
    variables.forEach(v => {
      text = text.replaceAll(`{{${v.name}}}`, v.default_value || `[${v.description}]`);
    });
    return text;
  }, [userTemplate, variables]);

  const addVariable = () => {
    setVariables([...variables, { name: '', type: 'string', description: '', default_value: '', required: true }]);
  };

  const removeVariable = (index: number) => {
    setVariables(variables.filter((_, i) => i !== index));
  };

  const updateVariable = (index: number, field: keyof Variable, value: any) => {
    const updated = [...variables];
    (updated[index] as any)[field] = value;
    setVariables(updated);
  };

  const handleSave = () => {
    message.success('提示词已保存');
    navigate('/prompts');
  };

  return (
    <div>
      <Space className="mb-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompts')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>提示词编辑器</Title>
      </Space>

      <Row gutter={16}>
        {/* 左侧：编辑区 */}
        <Col span={14}>
          <Card title="基础信息" size="small" className="mb-4">
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label="名称"><Input placeholder="task_contract_review" /></Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="分类">
                  <Select options={[
                    { value: 'system', label: '系统提示词' }, { value: 'task', label: '任务提示词' },
                    { value: 'dynamic', label: '动态提示词' }, { value: 'evaluation', label: '评估提示词' },
                  ]} defaultValue="task" />
                </Form.Item>
              </Col>
            </Row>
          </Card>

          <Card title="系统提示词 (System Prompt)" size="small" className="mb-4"
            extra={<Text type="secondary">定义Agent角色和行为约束</Text>}>
            <TextArea
              rows={6}
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              style={{ fontFamily: 'monospace', fontSize: 13 }}
              placeholder="定义Agent的角色、能力范围和行为约束..."
            />
          </Card>

          <Card title="用户提示词模板 (User Prompt Template)" size="small" className="mb-4"
            extra={
              <Space>
                <Text type="secondary">使用 {'{{变量名}}'} 定义动态变量</Text>
                <Switch checkedChildren="预览" unCheckedChildren="编辑" checked={previewMode} onChange={setPreviewMode} />
              </Space>
            }>
            {previewMode ? (
              <div className="p-3 bg-gray-50 rounded" style={{ minHeight: 200, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 13 }}>
                {previewText}
              </div>
            ) : (
              <TextArea
                rows={10}
                value={userTemplate}
                onChange={e => setUserTemplate(e.target.value)}
                style={{ fontFamily: 'monospace', fontSize: 13 }}
              />
            )}
          </Card>

          <Card title="输出配置" size="small">
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item label="输出格式">
                  <Select options={[
                    { value: 'markdown', label: 'Markdown' }, { value: 'json', label: 'JSON' },
                    { value: 'text', label: '纯文本' }, { value: 'structured', label: '结构化' },
                  ]} defaultValue="markdown" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="目标模型类型">
                  <Select options={[
                    { value: 'generation', label: '生成模型' }, { value: 'light', label: '轻量模型' },
                  ]} defaultValue="generation" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="目标Agent">
                  <Select options={[
                    { value: 'master', label: '主Agent' }, { value: 'compliance', label: '合规审查' },
                    { value: 'retrieval', label: '检索Agent' }, { value: 'drafting', label: '合同起草' },
                  ]} />
                </Form.Item>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 右侧：变量面板 */}
        <Col span={10}>
          <Card title="变量定义" size="small" className="mb-4"
            extra={<Button type="dashed" size="small" icon={<PlusOutlined />} onClick={addVariable}>添加变量</Button>}>
            {variables.map((v, i) => (
              <Card key={i} size="small" className="mb-2" style={{ background: '#fafafa' }}
                extra={<Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => removeVariable(i)} />}>
                <Row gutter={8}>
                  <Col span={12}>
                    <Input size="small" placeholder="变量名" value={v.name}
                      onChange={e => updateVariable(i, 'name', e.target.value)}
                      addonBefore="{{"} addonAfter="}}"
                    />
                  </Col>
                  <Col span={12}>
                    <Select size="small" style={{ width: '100%' }} value={v.type}
                      onChange={val => updateVariable(i, 'type', val)}
                      options={[
                        { value: 'string', label: '文本' }, { value: 'number', label: '数字' },
                        { value: 'boolean', label: '布尔' }, { value: 'array', label: '数组' },
                      ]}
                    />
                  </Col>
                </Row>
                <Input size="small" placeholder="变量描述" className="mt-1" value={v.description}
                  onChange={e => updateVariable(i, 'description', e.target.value)} />
                <Input size="small" placeholder="默认值" className="mt-1" value={v.default_value}
                  onChange={e => updateVariable(i, 'default_value', e.target.value)} />
                <div className="mt-1">
                  <Switch size="small" checked={v.required} onChange={val => updateVariable(i, 'required', val)} />
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>必填</Text>
                </div>
              </Card>
            ))}
          </Card>

          <Card title="模板预览" size="small" className="mb-4">
            <div className="p-3 bg-gray-50 rounded" style={{ maxHeight: 300, overflow: 'auto' }}>
              <Text strong className="block mb-2">系统提示词:</Text>
              <Paragraph style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{systemPrompt}</Paragraph>
              <Divider />
              <Text strong className="block mb-2">用户提示词(预览):</Text>
              <Paragraph style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{previewText}</Paragraph>
            </div>
          </Card>

          <Space className="w-full justify-end">
            <Button onClick={() => navigate('/prompts')}>取消</Button>
            <Button icon={<PlayCircleOutlined />} onClick={() => navigate('/prompts/test')}>测试</Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default PromptEditor;
