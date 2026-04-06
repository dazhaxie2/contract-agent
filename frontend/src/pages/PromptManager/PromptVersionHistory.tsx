import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Timeline, Tag, Typography, Button, Space, Row, Col, Descriptions } from 'antd';
import { ArrowLeftOutlined, RollbackOutlined, DiffOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const PromptVersionHistory: React.FC = () => {
  const navigate = useNavigate();

  const versions = [
    { version: 5, changelog: '优化引用格式要求，增加风险等级分类', created_at: '2024-03-15 14:30', author: '管理员', quality_score: 4.3, status: 'current' },
    { version: 4, changelog: '增加不确定内容声明规则', created_at: '2024-03-10 10:00', author: '管理员', quality_score: 4.1, status: '' },
    { version: 3, changelog: '调整温度参数建议，优化输出结构', created_at: '2024-02-28 16:20', author: '法务专家', quality_score: 3.9, status: '' },
    { version: 2, changelog: '增加合同起草模式支持', created_at: '2024-02-15 09:00', author: '管理员', quality_score: 3.7, status: '' },
    { version: 1, changelog: '初始版本', created_at: '2024-01-15 10:00', author: '管理员', quality_score: 3.5, status: '' },
  ];

  return (
    <div>
      <Space className="mb-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompts')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>提示词版本历史</Title>
        <Tag>法律专家系统提示词</Tag>
      </Space>

      <Row gutter={16}>
        <Col span={10}>
          <Card title="版本时间线" size="small">
            <Timeline
              items={versions.map(v => ({
                color: v.status === 'current' ? 'green' : 'blue',
                children: (
                  <div className="pb-3">
                    <Space className="mb-1">
                      <Tag color={v.status === 'current' ? 'success' : 'default'}>v{v.version}</Tag>
                      {v.status === 'current' && <Tag color="green">当前版本</Tag>}
                      {v.quality_score && <Text type="secondary">评分: {v.quality_score}/5</Text>}
                    </Space>
                    <div><Text>{v.changelog}</Text></div>
                    <div><Text type="secondary" style={{ fontSize: 12 }}>{v.created_at} · {v.author}</Text></div>
                    {v.status !== 'current' && (
                      <Button type="link" size="small" icon={<RollbackOutlined />} className="mt-1">回滚到此版本</Button>
                    )}
                  </div>
                ),
              }))}
            />
          </Card>
        </Col>

        <Col span={14}>
          <Card title="版本对比 (v4 → v5)" size="small" extra={<Button type="link" icon={<DiffOutlined />}>查看Diff</Button>}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="变更说明">优化引用格式要求，增加风险等级分类</Descriptions.Item>
              <Descriptions.Item label="变更时间">2024-03-15 14:30</Descriptions.Item>
              <Descriptions.Item label="变更人">管理员</Descriptions.Item>
            </Descriptions>

            <Title level={5} className="mt-4">系统提示词变更</Title>
            <div className="p-3 bg-gray-50 rounded mb-4" style={{ fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap' }}>
              <div>  你是一位资深合同合规法律专家。</div>
              <div>  ## 核心规则</div>
              <div>  1. 所有内容必须基于检索上下文，禁止编造</div>
              <div>  2. 必须标注引用来源</div>
              <div style={{ background: '#f6ffed', color: '#52c41a' }}>+ 3. 风险点需标注等级：高/中/低</div>
              <div style={{ background: '#f6ffed', color: '#52c41a' }}>+ 4. 引用格式：「依据《XX》第X条：xxx」</div>
              <div style={{ background: '#fff2e8', color: '#fa541c' }}>- 3. 不确定的内容必须声明</div>
              <div style={{ background: '#f6ffed', color: '#52c41a' }}>+ 5. 不确定内容声明：「暂无相关有效法律依据」</div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PromptVersionHistory;
