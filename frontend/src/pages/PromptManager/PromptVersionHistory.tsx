import React, { useEffect, useState } from 'react';
import { Button, Space, Table, Tag, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';

import { promptApi, PromptVersion } from '../../services/api';

const { Title, Text } = Typography;

const PromptVersionHistory: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    promptApi
      .getVersions(id)
      .then(setVersions)
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompts')}>
          返回
        </Button>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            版本历史
          </Title>
          <Text type="secondary">查看提示词模板的版本快照</Text>
        </div>
      </Space>
      <div className="panel-block">
        <Table
          rowKey="version"
          loading={loading}
          dataSource={versions}
          expandable={{
            expandedRowRender: (row) => <pre className="result-markdown">{row.user_prompt_template}</pre>,
          }}
          columns={[
            { title: '版本', dataIndex: 'version', render: (value) => <Tag>v{value}</Tag>, width: 100 },
            { title: '变更说明', dataIndex: 'change_log', render: (_, row) => row.change_log || row.changelog || '-' },
            { title: '输出格式', dataIndex: 'output_format', width: 120 },
            { title: '创建时间', dataIndex: 'created_at', width: 220 },
          ]}
        />
      </div>
    </Space>
  );
};

export default PromptVersionHistory;
