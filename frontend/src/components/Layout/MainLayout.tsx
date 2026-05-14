import React, { useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Avatar, Dropdown, Layout, Menu, Space, Typography, theme } from 'antd';
import {
  DashboardOutlined,
  FileProtectOutlined,
  FileTextOutlined,
  LogoutOutlined,
  MonitorOutlined,
  RobotOutlined,
  UserOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

const menuItems = [
  {
    key: '/reviews',
    icon: <FileProtectOutlined />,
    label: '合同审查',
  },
  {
    key: '/documents',
    icon: <FileTextOutlined />,
    label: '文档库',
  },
  {
    key: 'dashboard-group',
    icon: <DashboardOutlined />,
    label: '监控大盘',
    children: [
      { key: '/dashboard', label: '系统总览' },
      { key: '/dashboard/agent-trace', label: 'Agent 链路追踪' },
      { key: '/dashboard/retrieval', label: '检索质量' },
    ],
  },
  {
    key: 'model-group',
    icon: <RobotOutlined />,
    label: '模型配置',
    children: [
      { key: '/models', label: '模型列表' },
      { key: '/models/create', label: '新建模型' },
      { key: '/models/deployment', label: '部署管理' },
      { key: '/models/ab-test', label: 'A/B 测试' },
    ],
  },
  {
    key: 'prompt-group',
    icon: <MonitorOutlined />,
    label: '提示词管理',
    children: [
      { key: '/prompts', label: '模板列表' },
      { key: '/prompts/create', label: '新建模板' },
      { key: '/prompts/test', label: '提示词测试' },
    ],
  },
];

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  const userMenu = {
    items: [
      { key: 'profile', icon: <UserOutlined />, label: '个人设置' },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        navigate('/login', { replace: true });
      }
    },
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="dark" width={240}>
        <div className="layout-logo">
          <Typography.Title level={4} style={{ color: '#fff', margin: 0, fontSize: collapsed ? 14 : 16 }}>
            {collapsed ? 'CA' : '合同合规 Agent'}
          </Typography.Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={['dashboard-group', 'model-group', 'prompt-group']}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header className="app-header" style={{ background: colorBgContainer }}>
          <Typography.Text strong style={{ fontSize: 16 }}>
            合同合规智能 Agent 系统
          </Typography.Text>
          <Dropdown menu={userMenu}>
            <Space style={{ cursor: 'pointer' }}>
              <Avatar size="small" icon={<UserOutlined />} />
              <span>管理员</span>
            </Space>
          </Dropdown>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
