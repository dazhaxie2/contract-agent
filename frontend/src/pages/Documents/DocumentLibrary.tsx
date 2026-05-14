import React, { useEffect, useState } from 'react';
import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, FileTextOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';

import { documentApi, DocumentChunk, DocumentItem, IngestionJob } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

const typeLabels: Record<string, string> = {
  contract: '合同',
  law: '法律',
  regulation: '法规',
  case: '案例',
  guide: '指南',
};

const statusColor: Record<string, string> = {
  processed: 'green',
  uploaded: 'blue',
  processing: 'orange',
  failed: 'red',
};

const DocumentLibrary: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const loadDocuments = async (nextPage = page) => {
    setLoading(true);
    try {
      const data = await documentApi.list({
        page: nextPage,
        page_size: 10,
        search: search || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
      setPage(nextPage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments(1).catch(() => undefined);
  }, []);

  const openDetail = async (doc: DocumentItem) => {
    setSelected(doc);
    setDrawerOpen(true);
    setChunks([]);
    setJobs([]);
    const fullChunks = await documentApi.getChunks(doc.id, true);
    setChunks(fullChunks);
  };

  const deleteDoc = (doc: DocumentItem) => {
    Modal.confirm({
      title: '删除文档',
      content: `确认删除《${doc.title}》及其片段索引？`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        await documentApi.delete(doc.id);
        message.success('文档已删除');
        await loadDocuments(page);
      },
    });
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            文档库
          </Title>
          <Text type="secondary">查看合同、法规和检索片段的入库状态</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => loadDocuments(page)}>
          刷新
        </Button>
      </Space>

      <div className="panel-block">
        <Space style={{ marginBottom: 16 }}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索标题"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onPressEnter={() => loadDocuments(1)}
            style={{ width: 280 }}
          />
          <Button type="primary" onClick={() => loadDocuments(1)}>
            搜索
          </Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          pagination={{
            current: page,
            total,
            pageSize: 10,
            onChange: (next) => loadDocuments(next),
          }}
          columns={[
            {
              title: '标题',
              dataIndex: 'title',
              render: (value: string, row) => (
                <Button type="link" icon={<FileTextOutlined />} onClick={() => openDetail(row)}>
                  {value}
                </Button>
              ),
            },
            {
              title: '类型',
              dataIndex: 'doc_type',
              width: 100,
              render: (value: string) => typeLabels[value] || value,
            },
            {
              title: '状态',
              dataIndex: 'status',
              width: 120,
              render: (value: string) => <Tag color={statusColor[value] || 'default'}>{value}</Tag>,
            },
            { title: '片段数', dataIndex: 'chunk_count', width: 100 },
            { title: '文件名', dataIndex: 'file_name', ellipsis: true },
            { title: '上传时间', dataIndex: 'created_at', width: 220 },
            {
              title: '操作',
              width: 100,
              render: (_, row) => (
                <Button danger type="text" icon={<DeleteOutlined />} onClick={() => deleteDoc(row)}>
                  删除
                </Button>
              ),
            },
          ]}
        />
      </div>

      <Drawer title="文档详情" open={drawerOpen} onClose={() => setDrawerOpen(false)} width={720}>
        {selected ? (
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="标题">{selected.title}</Descriptions.Item>
              <Descriptions.Item label="类型">{typeLabels[selected.doc_type] || selected.doc_type}</Descriptions.Item>
              <Descriptions.Item label="状态">{selected.status}</Descriptions.Item>
              <Descriptions.Item label="文件">{selected.file_name}</Descriptions.Item>
              <Descriptions.Item label="大小">{selected.file_size} bytes</Descriptions.Item>
              <Descriptions.Item label="片段数">{selected.chunk_count}</Descriptions.Item>
              <Descriptions.Item label="生效">{selected.is_effective ? '是' : '否'}</Descriptions.Item>
              <Descriptions.Item label="失败原因">{selected.process_error || '-'}</Descriptions.Item>
            </Descriptions>

            <Title level={5}>入库事件</Title>
            {jobs.length ? (
              <Table rowKey="job_id" size="small" pagination={false} dataSource={jobs} columns={[]} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该版本暂未按文档聚合入库事件" />
            )}

            <Title level={5}>片段预览</Title>
            {chunks.length ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                {chunks.map((chunk) => (
                  <div key={chunk.id} className="chunk-preview">
                    <Space>
                      <Tag>{chunk.chunk_type}</Tag>
                      <Text type="secondary">{chunk.hierarchy_path || `片段 ${chunk.chunk_index + 1}`}</Text>
                    </Space>
                    <Paragraph ellipsis={{ rows: 4, expandable: true }}>{chunk.content}</Paragraph>
                  </div>
                ))}
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无片段" />
            )}
          </Space>
        ) : (
          <Empty />
        )}
      </Drawer>
    </Space>
  );
};

export default DocumentLibrary;
