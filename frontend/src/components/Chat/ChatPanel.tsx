import React, { useEffect, useRef, useState } from 'react';
import { Avatar, Button, Input, List, Space, Spin, Tag, Typography, Drawer, Descriptions, Empty } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, LinkOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { useChatStore, useAuthStore, type ChatMessage } from '../../store';
import { citationApi, type CitationDetail } from '../../services/api';

const { Text } = Typography;

interface ChatPanelProps {
  sessionId?: string;
  height?: number | string;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ sessionId: propSessionId, height = 520 }) => {
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [citation, setCitation] = useState<CitationDetail | null>(null);
  const [citationOpen, setCitationOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const auth = useAuthStore();
  const { activeSession, addMessage, updateMessage, appendMessageContent, createSession, activeSessionId, sessions } =
    useChatStore();

  const session = activeSession();
  const sid = propSessionId || activeSessionId || '';

  useEffect(() => {
    if (propSessionId && propSessionId !== activeSessionId) {
      const exists = sessions.some((s: { id: string }) => s.id === propSessionId);
      if (!exists) {
        createSession(propSessionId, 'New Chat');
      } else {
        useChatStore.getState().setActiveSession(propSessionId);
      }
    }
  }, [propSessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [session?.messages]);

  const sendStreamingMessage = async () => {
    const text = input.trim();
    if (!text || streaming) return;

    setStreaming(true);
    setInput('');

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    addMessage(sid, userMsg);

    const assistantMsgId = `assistant-${Date.now()}`;
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      streaming: true,
    };
    addMessage(sid, assistantMsg);

    abortRef.current = new AbortController();

    try {
      const res = await fetch('/api/v1/agents/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${auth.token}`,
          'X-Tenant-ID': auth.tenantId,
        },
        body: JSON.stringify({
          query: text,
          task_type: 'auto',
          session_id: sid,
          tenant_id: auth.tenantId,
        }),
        signal: abortRef.current.signal,
      });

      if (!res.body) throw new Error('No stream body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const payload = trimmed.slice(6);
          if (payload === '[DONE]') continue;

          try {
            const parsed = JSON.parse(payload);
            if (parsed.type === 'content' && parsed.text) {
              appendMessageContent(sid, assistantMsgId, parsed.text);
            } else if (parsed.type === 'references') {
              updateMessage(sid, assistantMsgId, { references: parsed.data });
            }
          } catch {
            appendMessageContent(sid, assistantMsgId, payload);
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        appendMessageContent(sid, assistantMsgId, `[Error] ${(err as Error).message}`);
      }
    } finally {
      updateMessage(sid, assistantMsgId, { streaming: false });
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const openCitation = async (id?: string) => {
    if (!id) return;
    setCitationOpen(true);
    setCitation(null);
    setCitation(await citationApi.get(id));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendStreamingMessage();
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height }}>
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '12px 8px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {(!session?.messages.length) && (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <RobotOutlined style={{ fontSize: 48, color: '#1677ff', marginBottom: 16 }} />
            <Typography.Text type="secondary">输入你的问题，我会智能调度专业Agent来处理</Typography.Text>
          </div>
        )}
        {session?.messages.map((msg: ChatMessage) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              gap: 8,
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              alignItems: 'flex-start',
            }}
          >
            <Avatar
              size={32}
              icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              style={{ flexShrink: 0, background: msg.role === 'user' ? '#1677ff' : '#52c41a' }}
            />
            <div
              style={{
                maxWidth: '75%',
                padding: '8px 12px',
                borderRadius: 12,
                background: msg.role === 'user' ? '#e6f4ff' : '#f5f5f5',
                border: '1px solid #f0f0f0',
              }}
            >
              <div style={{ lineHeight: 1.7 }}>
                <ReactMarkdown>{msg.content || (msg.streaming ? '...' : '')}</ReactMarkdown>
              </div>
              {msg.streaming && !msg.content && <Spin size="small" />}
              {msg.references && msg.references.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>引用依据：</Text>
                  <Space wrap size={4}>
                    {msg.references
                      .filter((r: Record<string, unknown>) => r.citation_id || r.citation_code)
                      .slice(0, 6)
                      .map((ref: Record<string, unknown>, i: number) => (
                        <Tag
                          key={i}
                          color="blue"
                          style={{ cursor: 'pointer' }}
                          onClick={() => openCitation(ref.citation_id as string)}
                        >
                          <LinkOutlined /> {String(ref.citation_code || ref.doc_title || `REF-${i + 1}`)}
                        </Tag>
                      ))}
                  </Space>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div style={{ padding: '12px 8px', borderTop: '1px solid #f0f0f0', display: 'flex', gap: 8 }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的需求，如：帮我审查这份合同的违约条款..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={streaming}
          style={{ flex: 1 }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={sendStreamingMessage}
          loading={streaming}
          style={{ alignSelf: 'flex-end' }}
        >
          发送
        </Button>
        {streaming && (
          <Button danger style={{ alignSelf: 'flex-end' }} onClick={() => abortRef.current?.abort()}>
            停止
          </Button>
        )}
      </div>

      <Drawer title="引用详情" open={citationOpen} onClose={() => setCitationOpen(false)} width={480}>
        {citation ? (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="引用编号">{citation.citation_code}</Descriptions.Item>
            <Descriptions.Item label="来源">{citation.title || '-'}</Descriptions.Item>
            <Descriptions.Item label="定位">{citation.locator || '-'}</Descriptions.Item>
          </Descriptions>
        ) : (
          <Empty description="加载中..." />
        )}
      </Drawer>
    </div>
  );
};

export default ChatPanel;
