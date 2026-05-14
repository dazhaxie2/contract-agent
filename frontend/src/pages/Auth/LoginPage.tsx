import React, { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { authApi } from '../../services/api';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (localStorage.getItem('access_token')) {
      navigate('/reviews', { replace: true });
    }
  }, [navigate]);

  const handleFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const token = await authApi.login(values.username, values.password);
      localStorage.setItem('access_token', token.access_token);
      localStorage.setItem('refresh_token', token.refresh_token);
      localStorage.setItem('tenant_id', 'default');
      message.success('登录成功');
      navigate('/reviews', { replace: true });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <Card className="login-card">
        <div style={{ marginBottom: 24 }}>
          <Title level={3} style={{ marginBottom: 8 }}>
            合同合规 Agent
          </Title>
          <Text type="secondary">登录后进入合同审查工作台</Text>
        </div>
        <Form
          layout="vertical"
          initialValues={{ username: 'admin', password: 'password123' }}
          onFinish={handleFinish}
        >
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} autoComplete="username" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
};

export default LoginPage;
