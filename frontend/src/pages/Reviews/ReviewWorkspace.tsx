import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Col,
  Collapse,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Progress,
  Rate,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Timeline,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  CopyOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  InboxOutlined,
  LinkOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';

import {
  agentApi,
  AgentExecution,
  citationApi,
  CitationDetail,
  documentApi,
  DocumentChunk,
  DocumentItem,
  IngestionJob,
  ReviewRiskItem,
  sessionApi,
} from '../../services/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const REVIEW_TYPES = [
  { value: 'general', label: '通用合同审查' },
  { value: 'purchase', label: '采购合同审查' },
  { value: 'lease', label: '租赁合同审查' },
  { value: 'labor', label: '劳动合同审查' },
  { value: 'clause_compare', label: '重点条款审查' },
];

const severityColor: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'green',
  uncertain: 'default',
};

const severityLabel: Record<string, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  uncertain: '不确定',
};

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function jobPercent(job?: IngestionJob | null) {
  if (!job) return 0;
  if (job.status === 'completed') return 100;
  if (job.status === 'failed') return 100;
  const stages: Record<string, number> = {
    uploaded: 20,
    preprocess: 40,
    chunked: 55,
    vectorized: 75,
    graph_indexed: 90,
  };
  return stages[job.stage] ?? 35;
}

function riskText(risk?: string) {
  if (!risk) return '未知';
  return severityLabel[risk] || risk;
}

const ReviewWorkspace: React.FC = () => {
  const [title, setTitle] = useState('');
  const [reviewType, setReviewType] = useState('general');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [execution, setExecution] = useState<AgentExecution | null>(null);
  const [history, setHistory] = useState<AgentExecution[]>([]);
  const [citation, setCitation] = useState<CitationDetail | null>(null);
  const [citationOpen, setCitationOpen] = useState(false);
  const [feedbackScore, setFeedbackScore] = useState(0);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const tenantId = localStorage.getItem('tenant_id') || 'default';
  const report = execution?.review_report;

  const refreshHistory = async () => {
    const data = await agentApi.listExecutions({ task_type: 'contract_review', page: 1, page_size: 10 });
    setHistory(data.items);
  };

  useEffect(() => {
    refreshHistory().catch(() => undefined);
  }, []);

  const selectedFile = useMemo(() => fileList[0]?.originFileObj as File | undefined, [fileList]);

  const runReview = async () => {
    if (!selectedFile) {
      message.warning('请先选择一份合同文件');
      return;
    }
    setBusy(true);
    setError('');
    setExecution(null);
    setDocument(null);
    setChunks([]);
    try {
      const uploaded = await documentApi.upload(selectedFile, {
        title: title || selectedFile.name,
        doc_type: 'contract',
        sync: false,
      });
      setJob(uploaded);

      let current = uploaded;
      for (let i = 0; i < 80 && current.status !== 'completed' && current.status !== 'failed'; i += 1) {
        await sleep(1500);
        current = await documentApi.getJob(uploaded.job_id);
        setJob(current);
      }
      if (current.status !== 'completed' || !current.doc_id) {
        throw new Error(current.error_message || '合同入库未完成');
      }

      const [doc, fullChunks] = await Promise.all([
        documentApi.get(current.doc_id),
        documentApi.getChunks(current.doc_id, true),
      ]);
      setDocument(doc);
      setChunks(fullChunks);

      const session = await sessionApi.create(`合同审查：${doc.title}`, {
        doc_id: doc.id,
        review_type: reviewType,
      });

      const reviewLabel = REVIEW_TYPES.find((item) => item.value === reviewType)?.label || '通用合同审查';
      const result = await agentApi.execute({
        query: `请对合同《${doc.title}》执行${reviewLabel}，输出总体风险、风险条目、法律依据和可执行修改建议。`,
        task_type: 'contract_review',
        session_id: session.id,
        tenant_id: tenantId,
        filters: { doc_id: doc.id },
      });
      setExecution(result);
      await refreshHistory();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '审查失败';
      setError(msg);
      message.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const loadHistory = async (row: AgentExecution) => {
    const id = row.execution_id || row.id;
    if (!id) return;
    const detail = await agentApi.getExecution(id);
    setExecution(detail);
    setFeedbackScore(0);
    setFeedbackComment('');
  };

  const openCitation = async (id?: string) => {
    if (!id) return;
    setCitationOpen(true);
    setCitation(null);
    setCitation(await citationApi.get(id));
  };

  const submitFeedback = async () => {
    const id = execution?.execution_id || execution?.id;
    if (!id || !feedbackScore) {
      message.warning('请选择评分');
      return;
    }
    await agentApi.submitFeedback(id, feedbackScore, feedbackComment);
    message.success('反馈已提交');
  };

  const copyMarkdown = async () => {
    if (!execution?.result) return;
    await navigator.clipboard.writeText(execution.result);
    message.success('审查结果已复制');
  };

  const downloadMarkdown = () => {
    if (!execution?.result) return;
    const blob = new Blob([execution.result], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement('a');
    link.href = url;
    link.download = `${document?.title || 'contract-review'}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const renderRisk = (item: ReviewRiskItem, index: number) => {
    const uncertain = item.severity === 'uncertain' || !item.references?.some((ref) => ref.citation_id);
    return (
      <div key={`${item.issue}-${index}`} className="risk-item">
        <Space style={{ marginBottom: 8 }}>
          <Tag color={severityColor[item.severity] || 'blue'}>{riskText(item.severity)}</Tag>
          {uncertain ? <Tag>依据不足</Tag> : null}
          <Text type="secondary">置信度 {Math.round((item.confidence || 0) * 100)}%</Text>
        </Space>
        <Paragraph strong>{item.issue}</Paragraph>
        <Paragraph>
          <Text type="secondary">相关条款：</Text>
          {item.clause_excerpt || '-'}
        </Paragraph>
        <Paragraph>
          <Text type="secondary">法律依据：</Text>
          {item.legal_basis || '未检索到可验证引用依据'}
        </Paragraph>
        <Paragraph>
          <Text type="secondary">修改建议：</Text>
          {item.recommendation}
        </Paragraph>
        <Space wrap>
          {(item.references || []).map((ref) => (
            <Button
              key={ref.citation_id || ref.chunk_id}
              size="small"
              icon={<LinkOutlined />}
              onClick={() => openCitation(ref.citation_id)}
              disabled={!ref.citation_id}
            >
              {ref.citation_code || ref.doc_title || '引用依据'}
            </Button>
          ))}
        </Space>
      </div>
    );
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            合同审查工作台
          </Title>
          <Text type="secondary">上传合同，生成可追溯的风险审查结论</Text>
        </div>
        <Button icon={<FileSearchOutlined />} onClick={refreshHistory}>
          刷新历史
        </Button>
      </Space>

      {error ? <Alert type="error" message={error} showIcon /> : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={9}>
          <div className="panel-block">
            <Title level={5}>新建审查</Title>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Input placeholder="合同标题" value={title} onChange={(e) => setTitle(e.target.value)} />
              <Select value={reviewType} options={REVIEW_TYPES} onChange={setReviewType} />
              <Upload.Dragger
                accept=".pdf,.doc,.docx,.txt,.md"
                maxCount={1}
                fileList={fileList}
                beforeUpload={(file) => {
                  setFileList([file]);
                  if (!title) setTitle(file.name);
                  return false;
                }}
                onRemove={() => setFileList([])}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">拖拽或点击选择合同文件</p>
              </Upload.Dragger>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={runReview} loading={busy} block>
                上传并开始审查
              </Button>
            </Space>
          </div>

          <div className="panel-block">
            <Title level={5}>入库进度</Title>
            {job ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Progress percent={jobPercent(job)} status={job.status === 'failed' ? 'exception' : undefined} />
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="状态">{job.status}</Descriptions.Item>
                  <Descriptions.Item label="阶段">{job.stage}</Descriptions.Item>
                  <Descriptions.Item label="文件">{job.file_name}</Descriptions.Item>
                  {job.error_message ? <Descriptions.Item label="错误">{job.error_message}</Descriptions.Item> : null}
                </Descriptions>
                <Timeline
                  items={(job.events || []).map((event) => ({
                    color: event.status === 'failed' ? 'red' : 'blue',
                    children: `${event.stage} · ${event.status}`,
                  }))}
                />
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无入库任务" />
            )}
          </div>
        </Col>

        <Col xs={24} lg={15}>
          <div className="panel-block">
            <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
              <Title level={5} style={{ margin: 0 }}>
                审查结果
              </Title>
              <Space>
                <Button icon={<CopyOutlined />} disabled={!execution?.result} onClick={copyMarkdown}>
                  复制
                </Button>
                <Button icon={<DownloadOutlined />} disabled={!execution?.result} onClick={downloadMarkdown}>
                  下载 Markdown
                </Button>
              </Space>
            </Space>

            {!execution ? (
              <Empty description="完成一次审查后在这里查看风险结论" />
            ) : (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Alert
                  type={report?.overall_risk === 'high' ? 'error' : report?.overall_risk === 'uncertain' ? 'warning' : 'info'}
                  message={`总体风险：${riskText(report?.overall_risk)}`}
                  description={report?.summary || execution.result}
                  showIcon
                />
                {(report?.risk_items || []).map(renderRisk)}
                <Collapse
                  items={[
                    {
                      key: 'markdown',
                      label: '完整 Markdown 结果',
                      children: <pre className="result-markdown">{execution.result}</pre>,
                    },
                    {
                      key: 'chunks',
                      label: `合同片段预览 ${chunks.length ? `(${chunks.length})` : ''}`,
                      children: chunks.length ? (
                        <Space direction="vertical" style={{ width: '100%' }}>
                          {chunks.slice(0, 6).map((chunk) => (
                            <div key={chunk.id} className="chunk-preview">
                              <Text type="secondary">{chunk.hierarchy_path || `片段 ${chunk.chunk_index + 1}`}</Text>
                              <Paragraph ellipsis={{ rows: 3, expandable: true }}>{chunk.content}</Paragraph>
                            </div>
                          ))}
                        </Space>
                      ) : (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="历史记录未加载合同片段" />
                      ),
                    },
                  ]}
                />
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text strong>人工反馈</Text>
                  <Rate value={feedbackScore} onChange={setFeedbackScore} />
                  <TextArea
                    rows={2}
                    placeholder="补充说明"
                    value={feedbackComment}
                    onChange={(event) => setFeedbackComment(event.target.value)}
                  />
                  <Button onClick={submitFeedback}>提交反馈</Button>
                </Space>
              </Space>
            )}
          </div>
        </Col>
      </Row>

      <div className="panel-block">
        <Title level={5}>最近审查</Title>
        <Table
          rowKey={(row) => row.execution_id || row.trace_id}
          size="small"
          dataSource={history}
          pagination={false}
          onRow={(row) => ({ onClick: () => loadHistory(row) })}
          columns={[
            { title: 'Trace ID', dataIndex: 'trace_id', ellipsis: true },
            { title: '状态', dataIndex: 'status', width: 100 },
            {
              title: '风险',
              width: 120,
              render: (_, row) => riskText(row.review_report?.overall_risk),
            },
            {
              title: '耗时',
              dataIndex: 'latency_ms',
              width: 110,
              render: (value: number) => `${Math.round(value || 0)} ms`,
            },
            { title: '创建时间', dataIndex: 'created_at', width: 220 },
          ]}
        />
      </div>

      <Drawer title="引用依据" open={citationOpen} onClose={() => setCitationOpen(false)} width={560}>
        {citation ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="引用编号">{citation.citation_code}</Descriptions.Item>
              <Descriptions.Item label="来源标题">{citation.title || '-'}</Descriptions.Item>
              <Descriptions.Item label="定位">{citation.locator || '-'}</Descriptions.Item>
              <Descriptions.Item label="文档 ID">{citation.document_id || '-'}</Descriptions.Item>
              <Descriptions.Item label="Chunk ID">{citation.chunk_id || '-'}</Descriptions.Item>
            </Descriptions>
            <Paragraph className="citation-excerpt">{citation.excerpt}</Paragraph>
          </Space>
        ) : (
          <Empty description="正在加载引用" />
        )}
      </Drawer>
    </Space>
  );
};

export default ReviewWorkspace;
