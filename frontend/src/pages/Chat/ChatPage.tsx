import React, { useState } from 'react';
import { Layout, Typography, Space, Button, List, Input } from 'antd';
import { PlusOutlined, MessageOutlined } from '@ant-design/icons';
import ChatPanel from '../../components/Chat/ChatPanel';
import { useChatStore, useAuthStore } from '../../store';
import { sessionApi } from '../../services/api';

const { Sider, Content } = Layout;
const { Text } = Typography;

const ChatPage: React.FC = () => {
  const auth = useAuthStore();
  const { sessions, activeSessionId, setActiveSession, createSession } = useChatStore();
  const [loading, setLoading] = useState(false);

  const handleNewChat = async () => {
    setLoading(true);
    try {
      const session = await sessionApi.create('New Chat', { mode: 'streaming_chat' });
      createSession(session.id, session.title);
    } catch {
      const id = `local-${Date.now()}`;
      createSession(id, 'New Chat');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout style={{ height: 'calc(100vh - 112px)', background: '#fff', borderRadius: 8 }}>
      <Sider width={240} theme="light" style={{ borderRight: '1px solid #f0f0f0' }}>
        <div style={{ padding: 12 }}>
          <Button type="primary" icon={<PlusOutlined />} block onClick={handleNewChat} loading={loading}>
            新建对话
          </Button>
        </div>
        <List
          size="small"
          dataSource={sessions}
          style={{ overflow: 'auto', maxHeight: 'calc(100vh - 200px)' }}
          renderItem={(item) => (
            <List.Item
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                background: item.id === activeSessionId ? '#e6f4ff' : 'transparent',
              }}
              onClick={() => setActiveSession(item.id)}
            >
              <Space>
                <MessageOutlined />
                <Text ellipsis style={{ maxWidth: 160 }}>{item.title}</Text>
              </Space>
            </List.Item>
          )}
        />
      </Sider>
      <Content>
        {activeSessionId ? (
          <ChatPanel sessionId={activeSessionId} height="calc(100vh - 112px)" />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Space direction="vertical" align="center">
              <MessageOutlined style={{ fontSize: 48, color: '#1677ff' }} />
              <Text type="secondary">点击"新建对话"开始</Text>
            </Space>
          </div>
        )}
      </Content>
    </Layout>
  );
};

export default ChatPage;
