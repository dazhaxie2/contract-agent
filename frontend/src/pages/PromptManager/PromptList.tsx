import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tag, Button, Space, Typography, Input, Select, Row, Col, Badge, Tooltip } from 'antd';
import { PlusOutlined, SearchOutlined, EditOutlined, HistoryOutlined, CopyOutlined, EyeOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const categoryColors: Record<string, string> = {
  system: 'red', task: 'blue', dynamic: 'green', evaluation: 'purple',
};
const categoryLabels: Record<string, string> = {
  system: '系统提示词', task: '任务提示词', dynamic: '动态提示词', evaluation: '评估提示词',
};
const statusColors: Record<string, string> = {
  draft: 'default', published: 'success', deprecated: 'warning',
};
const statusLabels: Record<string, string> = {
  draft: '草稿', published: '已发布', deprecated: '已废弃',
};

const PromptList: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const prompts = [
    { id: '1', name: 'system_legal_expert', display_name: '法律专家系统提示词', category: 'system', status: 'published', tags: ['合规', '通用'], current_version: 5, usage_count: 12580, avg_quality_score: 4.3, description: '定义Agent为资深合同合规法律专家角色，约束生成行为', user_prompt_template: '你是一位资深合同合规法律专家...' },
    { id: '2', name: 'task_contract_review', display_name: '合同审查任务提示词', category: 'task', status: 'published', tags: ['合同审查', '风险识别'], current_version: 8, usage_count: 5230, avg_quality_score: 4.1, description: '指导Agent完成合同合规性审查任务', user_prompt_template: '请对以下合同进行合规性审查...' },
    { id: '3', name: 'task_compliance_check', display_name: '合规校验任务提示词', category: 'task', status: 'published', tags: ['合规校验'], current_version: 3, usage_count: 3100, avg_quality_score: 4.0, description: '指导Agent完成合规校验任务', user_prompt_template: '请对以下内容进行合规性校验...' },
    { id: '4', name: 'task_clause_comparison', display_name: '条款比对任务提示词', category: 'task', status: 'draft', tags: ['条款比对', '版本对比'], current_version: 2, usage_count: 890, avg_quality_score: 3.8, description: '指导Agent完成合同条款版本比对', user_prompt_template: '请比对以下两个版本的合同条款...' },
    { id: '5', name: 'dynamic_context_inject', display_name: '动态上下文注入模板', category: 'dynamic', status: 'published', tags: ['上下文', '记忆'], current_version: 4, usage_count: 20000, avg_quality_score: null, description: '动态注入检索上下文、对话记忆、企业合规规则', user_prompt_template: '## 检索上下文\n{{context}}\n\n## 对话历史\n{{history}}' },
    { id: '6', name: 'eval_quality_check', display_name: '质量评估提示词', category: 'evaluation', status: 'published', tags: ['评估', '质量'], current_version: 2, usage_count: 8000, avg_quality_score: null, description: '用于评估Agent输出质量的评分提示词', user_prompt_template: '请从以下维度评分: 准确性、完整性、引用规范...' },
  ];

  const filtered = prompts.filter(p => {
    if (categoryFilter && p.category !== categoryFilter) return false;
    if (search && !p.display_name.includes(search) && !p.name.includes(search)) return false;
    return true;
  });

  // 按分类分组
  const grouped = filtered.reduce((acc, p) => {
    const cat = p.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(p);
    return acc;
  }, {} as Record<string, typeof prompts>);

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={4} style={{ margin: 0 }}>提示词模板管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/prompts/create')}>新建提示词</Button>
      </div>

      <Card size="small" className="mb-4">
        <Space>
          <Input placeholder="搜索提示词" prefix={<SearchOutlined />} style={{ width: 240 }} value={search} onChange={e => setSearch(e.target.value)} />
          <Select placeholder="分类" allowClear style={{ width: 150 }} value={categoryFilter || undefined} onChange={v => setCategoryFilter(v || '')}
            options={Object.entries(categoryLabels).map(([k, v]) => ({ value: k, label: v }))}
          />
        </Space>
      </Card>

      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="mb-6">
          <Title level={5}>
            <Tag color={categoryColors[category]}>{categoryLabels[category]}</Tag>
            <Text type="secondary" style={{ fontSize: 14 }}>({items.length}个)</Text>
          </Title>
          <Row gutter={[16, 16]}>
            {items.map((prompt) => (
              <Col key={prompt.id} xs={24} md={12} lg={8}>
                <Card
                  hoverable
                  size="small"
                  title={
                    <Space>
                      <Text strong>{prompt.display_name}</Text>
                      <Badge status={statusColors[prompt.status] as any} text={statusLabels[prompt.status]} />
                    </Space>
                  }
                  extra={<Text type="secondary">v{prompt.current_version}</Text>}
                  actions={[
                    <Tooltip title="编辑" key="edit"><EditOutlined onClick={() => navigate(`/prompts/${prompt.id}/edit`)} /></Tooltip>,
                    <Tooltip title="版本历史" key="history"><HistoryOutlined onClick={() => navigate(`/prompts/${prompt.id}/history`)} /></Tooltip>,
                    <Tooltip title="测试" key="test"><EyeOutlined onClick={() => navigate('/prompts/test')} /></Tooltip>,
                  ]}
                >
                  <Paragraph ellipsis={{ rows: 2 }} type="secondary" style={{ marginBottom: 8 }}>
                    {prompt.description}
                  </Paragraph>
                  <div className="mb-2">
                    {prompt.tags.map(tag => <Tag key={tag} style={{ marginBottom: 4 }}>{tag}</Tag>)}
                  </div>
                  <Space split={<Text type="secondary">|</Text>}>
                    <Text type="secondary" style={{ fontSize: 12 }}>使用 {prompt.usage_count} 次</Text>
                    {prompt.avg_quality_score && <Text type="secondary" style={{ fontSize: 12 }}>评分 {prompt.avg_quality_score}/5</Text>}
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      ))}
    </div>
  );
};

export default PromptList;
