import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Select, Slider, InputNumber, Switch, Button, Card, Row, Col, Typography, Divider, Space, message } from 'antd';
import { SaveOutlined, ArrowLeftOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;

const ModelConfigForm: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const onFinish = (values: any) => {
    console.log('提交:', values);
    message.success('模型配置已保存');
    navigate('/models');
  };

  return (
    <div>
      <Space className="mb-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/models')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>新建模型配置</Title>
      </Space>

      <Form form={form} layout="vertical" onFinish={onFinish}
        initialValues={{ provider: 'aliyun', model_type: 'generation', temperature: 0.1, top_p: 0.8, max_tokens: 8192, context_window: 32768, timeout_seconds: 120, max_retries: 3, max_concurrent_requests: 50, requests_per_minute: 600, supports_streaming: true, supports_function_calling: false }}
      >
        <Row gutter={24}>
          <Col span={12}>
            <Card title="基础信息" size="small" className="mb-4">
              <Form.Item label="配置名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
                <Input placeholder="如: qwen-max-legal" />
              </Form.Item>
              <Form.Item label="显示名称" name="display_name" rules={[{ required: true }]}>
                <Input placeholder="如: 通义千问Max(法律版)" />
              </Form.Item>
              <Form.Item label="描述" name="description">
                <TextArea rows={2} placeholder="模型用途描述" />
              </Form.Item>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="模型类型" name="model_type" rules={[{ required: true }]}>
                    <Select options={[
                      { value: 'generation', label: '核心生成模型' },
                      { value: 'light', label: '轻量预处理模型' },
                      { value: 'embedding', label: '嵌入模型' },
                      { value: 'reranker', label: '重排模型' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="提供商" name="provider" rules={[{ required: true }]}>
                    <Select options={[
                      { value: 'aliyun', label: '阿里云通义千问' },
                      { value: 'openai', label: 'OpenAI' },
                      { value: 'local', label: '本地部署' },
                      { value: 'vllm', label: 'vLLM推理' },
                    ]} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="模型ID" name="model_id" rules={[{ required: true }]}>
                <Input placeholder="如: qwen-max / gpt-4o" />
              </Form.Item>
            </Card>

            <Card title="端点配置" size="small">
              <Form.Item label="API端点" name="api_endpoint">
                <Input placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
              </Form.Item>
              <Form.Item label="API Key" name="api_key">
                <Input.Password placeholder="sk-..." />
              </Form.Item>
            </Card>
          </Col>

          <Col span={12}>
            <Card title="模型参数" size="small" className="mb-4">
              <Form.Item label={<Space>Temperature <Text type="secondary">控制生成随机性，合规场景建议0.1-0.3</Text></Space>} name="temperature">
                <Slider min={0} max={2} step={0.05} marks={{ 0: '精确', 0.3: '推荐', 1: '创意', 2: '随机' }} />
              </Form.Item>
              <Form.Item label="Top-P" name="top_p">
                <Slider min={0} max={1} step={0.05} marks={{ 0: '0', 0.8: '推荐', 1: '1.0' }} />
              </Form.Item>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="最大Token数" name="max_tokens">
                    <InputNumber min={1} max={1000000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="上下文窗口" name="context_window">
                    <InputNumber min={1024} max={1000000} style={{ width: '100%' }} addonAfter="tokens" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="支持流式输出" name="supports_streaming" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="支持函数调用" name="supports_function_calling" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>
            </Card>

            <Card title="性能与限流" size="small">
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="超时时间(秒)" name="timeout_seconds">
                    <InputNumber min={1} max={600} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="最大重试次数" name="max_retries">
                    <InputNumber min={0} max={10} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="最大并发请求" name="max_concurrent_requests">
                    <InputNumber min={1} max={1000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="每分钟请求限制" name="requests_per_minute">
                    <InputNumber min={1} max={100000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>

        <div className="mt-4 text-right">
          <Space>
            <Button onClick={() => navigate('/models')}>取消</Button>
            <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>保存配置</Button>
          </Space>
        </div>
      </Form>
    </div>
  );
};

export default ModelConfigForm;
