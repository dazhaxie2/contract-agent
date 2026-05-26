import React, { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Drawer,
  Empty,
  Modal,
  Progress,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import type { RcFile } from 'antd/es/upload/interface';
import {
  DeleteOutlined,
  InboxOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';

import { documentApi, DocumentChunk, DocumentItem, IngestionJob } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

const DOC_TYPE = 'enterprise_rule';

const statusColor: Record<string, string> = {
  processed: 'green',
  completed: 'green',
  uploaded: 'blue',
  processing: 'orange',
  failed: 'red',
};

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

const EnterpriseRules: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [uploadJob, setUploadJob] = useState<IngestionJob | null>(null);
  const [selected, setSelected] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadRules = async (nextPage = page) => {
    setLoading(true);
    try {
      const data = await documentApi.list({ doc_type: DOC_TYPE, page: nextPage, page_size: 10 });
      setItems(data.items);
      setTotal(data.total);
      setPage(nextPage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules(1).catch(() => undefined);
  }, []);

  const handleUpload = async (file: RcFile) => {
    setUploading(true);
    setUploadJob(null);
    try {
      const uploaded = await documentApi.upload(file, { title: file.name, doc_type: DOC_TYPE, sync: false });
      setUploadJob(uploaded);
      let current = uploaded;
      for (let i = 0; i < 80 && current.status !== 'completed' && current.status !== 'failed'; i += 1) {
        await sleep(1500);
        current = await documentApi.getJob(uploaded.job_id);
        setUploadJob(current);
      }
      if (current.status === 'completed') {
        message.success(`《${file.name}》已入库`);
        await loadRules(1);
      } else {
        message.error(current.error_message || '制度入库未完成');
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const openDetail = async (doc: DocumentItem) => {
    setSelected(doc);
    setDrawerOpen(true);
    setChunks([]);
    setDetailLoading(true);
    try {
      setChunks(await documentApi.getChunks(doc.id, true));
    } finally {
      setDetailLoading(false);
    }
  };

  const deleteRule = (doc: DocumentItem) => {
    Modal.confirm({
      title: '删除制度',
      content: `确认删除《${doc.title}》及其片段索引？删除后不再参与合同审查比对。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        await documentApi.delete(doc.id);
        message.success('制度已删除');
        await loadRules(page);
      },
    });
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
        <div>
          <Title level={4} style={{ margin: 0 }}>
            企业制度库
          </Title>
          <Text type="secondary">沉淀企业自有规章制度，审查合同时自动比对，作为“企业制度依据”进入审查报告</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => loadRules(page)}>
          刷新
        </Button>
      </Space>

      <Alert
        type="info"
        showIcon
        icon={<SafetyCertificateOutlined />}
        message="企业制度与法律法规分开管理"
        description="这里上传的制度面向整个租户，会在合同审查时独立检索，并在结论中和外部法律依据区分标注。"
      />

      <div className="panel-block">
        <Upload.Dragger
          accept=".pdf,.doc,.docx,.txt,.md"
          showUploadList={false}
          disabled={uploading}
          beforeUpload={(file) => {
            handleUpload(file as RcFile);
            return false;
          }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">拖拽或点击上传企业制度文件</p>
          <p className="ant-upload-hint">支持 PDF / Word / TXT / Markdown，例如采购制度、用印制度、合同管理办法</p>
        </Upload.Dragger>
        {uploadJob ? (
          <div style={{ marginTop: 12 }}>
            <Progress
              percent={uploadJob.status === 'completed' ? 100 : uploadJob.status === 'failed' ? 100 : 60}
              status={uploadJob.status === 'failed' ? 'exception' : uploadJob.status === 'completed' ? 'success' : 'active'}
            />
            <Text type="secondary">
              {uploadJob.file_name} · {uploadJob.status}
              {uploadJob.error_message ? ` · ${uploadJob.error_message}` : ''}
            </Text>
          </div>
        ) : null}
      </div>

      <div className="panel-block">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          pagination={{ current: page, total, pageSize: 10, onChange: (next) => loadRules(next) }}
          locale={{ emptyText: <Empty description="还没有企业制度，先上传一份" /> }}
          columns={[
            {
              title: '制度名称',
              dataIndex: 'title',
              render: (value: string, row) => (
                <Button type="link" onClick={() => openDetail(row)}>
                  {value}
                </Button>
              ),
            },
            {
              title: '状态',
              dataIndex: 'status',
              width: 120,
              render: (value: string) => <Tag color={statusColor[value] || 'default'}>{value}</Tag>,
            },
            { title: '片段数', dataIndex: 'chunk_count', width: 100 },
            { title: '生效', dataIndex: 'is_effective', width: 80, render: (value: boolean) => (value ? '是' : '否') },
            { title: '上传时间', dataIndex: 'created_at', width: 200 },
            {
              title: '操作',
              width: 100,
              render: (_, row) => (
                <Button danger type="text" icon={<DeleteOutlined />} onClick={() => deleteRule(row)}>
                  删除
                </Button>
              ),
            },
          ]}
        />
      </div>

      <Drawer title="制度详情" open={drawerOpen} onClose={() => setDrawerOpen(false)} width={680}>
        {selected ? (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Title level={5} style={{ margin: 0 }}>
              {selected.title}
            </Title>
            <Text type="secondary">
              状态 {selected.status} · 片段 {selected.chunk_count} · {selected.file_name}
            </Text>
            {detailLoading ? (
              <Skeleton active paragraph={{ rows: 4 }} />
            ) : chunks.length ? (
              chunks.map((chunk) => (
                <div key={chunk.id} className="chunk-preview">
                  <Text type="secondary">{chunk.hierarchy_path || `片段 ${chunk.chunk_index + 1}`}</Text>
                  <Paragraph ellipsis={{ rows: 4, expandable: true }}>{chunk.content}</Paragraph>
                </div>
              ))
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

export default EnterpriseRules;
