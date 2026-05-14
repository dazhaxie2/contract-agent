import React, { useEffect, useState } from 'react';
import { Button, Input, Select, Space, Table, Tag, Typography } from 'antd';
import { EditOutlined, HistoryOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { promptApi, PromptTemplate } from '../../services/api';

const { Title, Text } = Typography;

const categoryLabels: Record<string, string> = {
  system: '系统提示词',
  task: '任务提示词',
  dynamic: '动态提示词',
  evaluation: '评估提示词',
};

const PromptList: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<PromptTemplate[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await promptApi.list({ page: 1, page_size: 50, search: search || undefined, category: category || undefined });
      setItems(data.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            提示词模板
          </Title>
          <Text type="secondary">管理 Agent 使用的系统提示词和任务模板</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/prompts/create')}>
          新建模板
        </Button>
      </Space>

      <div className="panel-block">
        <Space style={{ marginBottom: 16 }}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索模板"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onPressEnter={load}
            style={{ width: 260 }}
          />
          <Select
            allowClear
            placeholder="分类"
            value={category || undefined}
            onChange={(value) => setCategory(value || '')}
            options={Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))}
            style={{ width: 160 }}
          />
          <Button onClick={load}>查询</Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          columns={[
            { title: '名称', dataIndex: 'display_name', render: (value, row) => value || row.name },
            { title: '标识', dataIndex: 'name' },
            {
              title: '分类',
              dataIndex: 'category',
              width: 140,
              render: (value: string) => categoryLabels[value] || value,
            },
            {
              title: '状态',
              dataIndex: 'status',
              width: 120,
              render: (value: string) => <Tag>{value}</Tag>,
            },
            { title: '版本', dataIndex: 'current_version', width: 100 },
            { title: '使用次数', dataIndex: 'usage_count', width: 120 },
            {
              title: '操作',
              width: 180,
              render: (_, row) => (
                <Space>
                  <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/prompts/${row.id}/edit`)}>
                    编辑
                  </Button>
                  <Button size="small" icon={<HistoryOutlined />} onClick={() => navigate(`/prompts/${row.id}/history`)}>
                    版本
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </div>
    </Space>
  );
};

export default PromptList;
