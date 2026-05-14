import React, { useEffect, useState } from 'react';
import { Button, Form, Input, Select, Space, Typography, message } from 'antd';
import { ArrowLeftOutlined, SaveOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';

import { promptApi, PromptTemplate } from '../../services/api';

const { Title, Text } = Typography;
const { TextArea } = Input;

const PromptEditor: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    promptApi
      .get(id)
      .then((tpl: PromptTemplate) => {
        form.setFieldsValue({
          ...tpl,
          variables_json: JSON.stringify(tpl.variables || [], null, 2),
          tags_text: (tpl.tags || []).join(','),
        });
      })
      .finally(() => setLoading(false));
  }, [form, id]);

  const handleSave = async () => {
    const values = await form.validateFields();
    let variables = [];
    try {
      variables = values.variables_json ? JSON.parse(values.variables_json) : [];
    } catch {
      message.error('变量定义必须是合法 JSON');
      return;
    }
    const payload = {
      name: values.name,
      display_name: values.display_name,
      description: values.description || '',
      category: values.category,
      task_type: values.task_type || '',
      system_prompt: values.system_prompt || '',
      user_prompt_template: values.user_prompt_template,
      variables,
      target_model_type: values.target_model_type || 'generation',
      target_agent: values.target_agent || 'master',
      output_format: values.output_format || 'text',
      validation_rules: [],
      tags: String(values.tags_text || '')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      changelog: values.changelog || 'update prompt',
    };

    setLoading(true);
    try {
      if (id) {
        await promptApi.update(id, payload);
      } else {
        await promptApi.create(payload);
      }
      message.success('提示词已保存');
      navigate('/prompts');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompts')}>
          返回
        </Button>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            {id ? '编辑提示词' : '新建提示词'}
          </Title>
          <Text type="secondary">保存后会生成新的版本快照</Text>
        </div>
      </Space>

      <div className="panel-block">
        <Form
          form={form}
          layout="vertical"
          disabled={loading}
          initialValues={{
            category: 'task',
            output_format: 'text',
            target_agent: 'master',
            target_model_type: 'generation',
            variables_json: '[\n  {"name": "content", "type": "string", "default_value": "", "description": "合同内容", "required": true}\n]',
          }}
        >
          <Form.Item label="模板标识" name="name" rules={[{ required: true, message: '请输入模板标识' }]}>
            <Input disabled={Boolean(id)} placeholder="task_contract_review" />
          </Form.Item>
          <Form.Item label="显示名称" name="display_name" rules={[{ required: true, message: '请输入显示名称' }]}>
            <Input placeholder="合同审查提示词" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input />
          </Form.Item>
          <Space size={16} style={{ width: '100%' }}>
            <Form.Item label="分类" name="category" rules={[{ required: true }]} style={{ width: 180 }}>
              <Select
                options={[
                  { value: 'system', label: '系统提示词' },
                  { value: 'task', label: '任务提示词' },
                  { value: 'dynamic', label: '动态提示词' },
                  { value: 'evaluation', label: '评估提示词' },
                ]}
              />
            </Form.Item>
            <Form.Item label="输出格式" name="output_format" style={{ width: 180 }}>
              <Select
                options={[
                  { value: 'text', label: 'Text' },
                  { value: 'markdown', label: 'Markdown' },
                  { value: 'json', label: 'JSON' },
                ]}
              />
            </Form.Item>
            <Form.Item label="目标 Agent" name="target_agent" style={{ width: 180 }}>
              <Select options={[{ value: 'master', label: 'Master Agent' }]} />
            </Form.Item>
          </Space>
          <Form.Item label="系统提示词" name="system_prompt">
            <TextArea rows={6} className="code-editor" />
          </Form.Item>
          <Form.Item label="用户提示词模板" name="user_prompt_template" rules={[{ required: true, message: '请输入模板内容' }]}>
            <TextArea rows={10} className="code-editor" placeholder="请审查：{{content}}" />
          </Form.Item>
          <Form.Item label="变量定义 JSON" name="variables_json">
            <TextArea rows={5} className="code-editor" />
          </Form.Item>
          <Form.Item label="标签，逗号分隔" name="tags_text">
            <Input placeholder="合同审查,风险识别" />
          </Form.Item>
          <Form.Item label="变更说明" name="changelog">
            <Input placeholder="更新审查输出格式" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={handleSave}>
            保存
          </Button>
        </Form>
      </div>
    </Space>
  );
};

export default PromptEditor;
