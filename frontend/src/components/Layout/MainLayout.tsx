import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, theme, Typography, Avatar, Dropdown, Space } from 'antd';
import {
  DashboardOutlined, RobotOutlined, FileTextOutlined,
  SettingOutlined, ExperimentOutlined, ApiOutlined,
  MonitorOutlined, NodeIndexOutlined, SearchOutlined,
  UserOutlined, LogoutOutlined, BellOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

const menuItems = [
  {
    key: 'dashboard-group',
    icon: <DashboardOutlined />,
    label: '监控大盘',
    children: [
      { key: '/dashboard', label: '系统总览' },
      { key: '/dashboard/agent-trace', label: 'Agent链路追踪' },
      { key: '/dashboard/retrieval', label: '检索质量大盘' },
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
      { key: '/models/ab-test', label: 'A/B测试' },
    ],
  },
  {
    key: 'prompt-group',
    icon: <FileTextOutlined />,
    label: '提示词管理',
    children: [
      { key: '/prompts', label: '提示词列表' },
      { key: '/prompts/create', label: '新建提示词' },
      { key: '/prompts/test', label: '提示词测试' },
    ],
  },
];

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();

  const userMenu = {
    items: [
      { key: 'profile', icon: <UserOutlined />, label: '个人设置' },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
    ],
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={240}
      >
        <div className="flex items-center justify-center h-16 m-4">
          <Typography.Title level={4} style={{ color: '#fff', margin: 0, fontSize: collapsed ? 14 : 16 }}>
            {collapsed ? 'CA' : '合同合规Agent'}
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
        <Header style={{ padding: '0 24px', background: colorBgContainer, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography.Text strong style={{ fontSize: 16 }}>
            合同合规智能Agent系统
          </Typography.Text>
          <Space size="large">
            <BellOutlined style={{ fontSize: 18 }} />
            <Dropdown menu={userMenu}>
              <Space style={{ cursor: 'pointer' }}>
                <Avatar size="small" icon={<UserOutlined />} />
                <span>管理员</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: 16 }}>
          <div style={{ padding: 24, background: colorBgContainer, borderRadius: borderRadiusLG, minHeight: 'calc(100vh - 128px)' }}>
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
