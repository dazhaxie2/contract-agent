import React, { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { AxiosError } from 'axios';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { authApi } from '../../services/api';
import { useAuthStore } from '../../store';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const auth = useAuthStore();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (localStorage.getItem('access_token')) {
      navigate('/chat', { replace: true });
    }
  }, [navigate]);

  const handleFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const token = await authApi.login(values.username, values.password);
      if (!token?.access_token) {
        throw new Error('登录返回缺少 access_token');
      }
      auth.login(token.access_token, token.refresh_token, 'default');
      message.success('登录成功');
      navigate('/chat', { replace: true });
    } catch (e) {
      const err = e as AxiosError<{ detail?: string; message?: string }>;
      const detail = err.response?.data?.detail || err.response?.data?.message;
      message.error(detail || err.message || '登录失败，请检查账号密码');
      console.error('[login] failed', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <Card className="login-card">
        <div style={{ marginBottom: 24 }}>
          <Title level={4} style={{ marginBottom: 8 }}>
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
