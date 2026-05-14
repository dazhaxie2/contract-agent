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
  List,
  Progress,
  Rate,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Timeline,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import { useSearchParams } from 'react-router-dom';
import {
  CheckCircleOutlined,
  CopyOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  InboxOutlined,
  LinkOutlined,
  PlayCircleOutlined,
  SendOutlined,
} from '@ant-design/icons';

import {
  agentApi,
  AgentExecution,
  AgentPlan,
  citationApi,
  CitationDetail,
  documentApi,
  DocumentChunk,
  DocumentItem,
  IngestionJob,
  PlanStep,
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

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  plan?: AgentPlan;
}

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

function normalizePlan(plan?: AgentExecution['plan']): AgentPlan | null {
  if (!plan || typeof plan !== 'object') return null;
  const candidate = plan as AgentPlan;
  return candidate.decision_id && Array.isArray(candidate.steps) ? candidate : null;
}

function uploadItemToFile(item?: UploadFile): File | undefined {
  return (item?.originFileObj as File | undefined) || (item as unknown as File | undefined);
}

const ReviewWorkspace: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [title, setTitle] = useState('');
  const [reviewType, setReviewType] = useState('general');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [activeDocument, setActiveDocument] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '把合同拖到左侧，然后直接说你想怎么审。我会先生成执行计划，确认后再写入审查记录。',
    },
  ]);
  const [currentPlan, setCurrentPlan] = useState<AgentPlan | null>(null);
  const [execution, setExecution] = useState<AgentExecution | null>(null);
  const [history, setHistory] = useState<AgentExecution[]>([]);
  const [citation, setCitation] = useState<CitationDetail | null>(null);
  const [citationOpen, setCitationOpen] = useState(false);
  const [feedbackScore, setFeedbackScore] = useState(0);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState('');
  const [error, setError] = useState('');

  const tenantId = localStorage.getItem('tenant_id') || 'default';
  const selectedFile = useMemo(() => uploadItemToFile(fileList[0]), [fileList]);
  const report = execution?.review_report;

  const createMessageId = (index: number) =>
    window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${index}`;

  const addMessage = (role: ChatMessage['role'], content: string, plan?: AgentPlan) => {
    setChatMessages((items) => [...items, { id: createMessageId(items.length), role, content, plan }]);
  };

  const refreshHistory = async () => {
    const data = await agentApi.listExecutions({ task_type: 'contract_review', page: 1, page_size: 10 });
    setHistory(data.items);
  };

  useEffect(() => {
    refreshHistory().catch(() => undefined);
  }, []);

  useEffect(() => {
    const docId = searchParams.get('doc_id');
    if (!docId || activeDocument?.id === docId) return;

    let cancelled = false;
    const preloadDocument = async () => {
      setBusy(true);
      setBusyLabel('加载文档');
      setError('');
      try {
        const [doc, fullChunks] = await Promise.all([
          documentApi.get(docId),
          documentApi.getChunks(docId, true),
        ]);
        if (cancelled) return;
        const nextReviewType = searchParams.get('review_type') || 'general';
        const mode = searchParams.get('mode');
        setActiveDocument(doc);
        setChunks(fullChunks);
        setTitle(doc.title);
        setReviewType(nextReviewType);
        setFileList([]);
        setJob(null);
        setCurrentPlan(null);
        setExecution(null);
        setChatInput(
          mode === 'compare'
            ? `基于文档库中的《${doc.title}》发起版本对比，重点看风险变化、付款、违约和责任限制。`
            : `帮我审文档库中的《${doc.title}》，重点看付款、违约、解除、保密、责任限制和争议解决。`,
        );
        addMessage('assistant', `已从文档库载入《${doc.title}》，可以直接生成审查计划。`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : '加载文档失败';
        setError(msg);
        message.error(msg);
      } finally {
        if (!cancelled) {
          setBusy(false);
          setBusyLabel('');
        }
      }
    };

    preloadDocument();
    return () => {
      cancelled = true;
    };
  }, [searchParams, activeDocument?.id]);

  const ensureSession = async (doc?: DocumentItem | null) => {
    if (sessionId) return sessionId;
    const session = await sessionApi.create(doc ? `合同助手：${doc.title}` : '合同助手会话', {
      mode: 'plan_confirm_review',
      doc_id: doc?.id,
      review_type: reviewType,
    });
    setSessionId(session.id);
    return session.id;
  };

  const ingestFile = async (file: File, displayTitle?: string) => {
    const uploaded = await documentApi.upload(file, {
      title: displayTitle || file.name,
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
    return { doc, fullChunks };
  };

  const prepareContract = async () => {
    if (activeDocument) return activeDocument;
    if (!selectedFile) return null;

    setBusyLabel('合同入库中');
    const { doc, fullChunks } = await ingestFile(selectedFile, title || selectedFile.name);
    setActiveDocument(doc);
    setChunks(fullChunks);
    return doc;
  };

  const defaultQuery = (doc?: DocumentItem | null) => {
    const reviewLabel = REVIEW_TYPES.find((item) => item.value === reviewType)?.label || '通用合同审查';
    const docName = doc?.title || title || selectedFile?.name || '这份合同';
    return `帮我审${docName}，按${reviewLabel}重点看付款、违约、解除、保密、责任限制和争议解决，并生成修改建议和 Markdown 报告。`;
  };

  const createPlan = async (queryText?: string) => {
    const userQuery = (queryText || chatInput).trim();
    if (!userQuery && !selectedFile && !activeDocument) {
      message.warning('请先输入需求或选择合同文件');
      return;
    }

    setBusy(true);
    setBusyLabel('生成执行计划');
    setError('');
    setCurrentPlan(null);
    setExecution(null);
    if (userQuery) addMessage('user', userQuery);
    setChatInput('');

    try {
      const doc = await prepareContract();
      const sid = await ensureSession(doc);
      const query = userQuery || defaultQuery(doc);
      if (!userQuery) addMessage('user', query);

      const filters = doc ? { doc_id: doc.id, document_ids: [doc.id] } : {};
      const plan = await agentApi.plan({
        query,
        session_id: sid,
        tenant_id: tenantId,
        task_type: 'contract_review',
        filters,
        context: {
          doc_id: doc?.id,
          document_ids: doc ? [doc.id] : [],
          doc_title: doc?.title,
          review_type: reviewType,
          source: 'contract_assistant_workspace',
        },
      });
      setCurrentPlan(plan);
      addMessage('assistant', '我已经拆成可确认的执行计划。确认后会开始审查，并把 decision_id、计划和工具轨迹写入历史。', plan);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成计划失败';
      setError(msg);
      message.error(msg);
    } finally {
      setBusy(false);
      setBusyLabel('');
    }
  };

  const confirmPlan = async (plan: AgentPlan) => {
    setBusy(true);
    setBusyLabel('执行审查计划');
    setError('');
    try {
      addMessage('assistant', `已确认计划 ${plan.decision_id}，开始执行审查。`);
      const result = await agentApi.executeDecision(plan.decision_id, {
        confirmed: true,
        comment: '用户在合同助手工作台确认执行计划',
      });
      setExecution(result);
      setCurrentPlan(normalizePlan(result.plan) || plan);
      setFeedbackScore(0);
      setFeedbackComment('');
      addMessage('assistant', '审查完成。右侧工作台已经更新风险清单、引用依据和 Markdown 报告。');
      await refreshHistory();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '执行计划失败';
      setError(msg);
      message.error(msg);
    } finally {
      setBusy(false);
      setBusyLabel('');
    }
  };

  const runBatchReview = async () => {
    const files = fileList.map(uploadItemToFile).filter((item): item is File => Boolean(item));
    if (!files.length) {
      message.warning('请先选择合同文件');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const results: AgentExecution[] = [];
      for (const file of files) {
        setBusyLabel(`批量审查：${file.name}`);
        const { doc, fullChunks } = await ingestFile(file, file.name);
        const session = await sessionApi.create(`批量合同审查：${doc.title}`, {
          mode: 'batch_review',
          doc_id: doc.id,
          review_type: reviewType,
        });
        const query = defaultQuery(doc);
        const plan = await agentApi.plan({
          query,
          session_id: session.id,
          tenant_id: tenantId,
          task_type: 'contract_review',
          filters: { doc_id: doc.id, document_ids: [doc.id] },
          context: {
            doc_id: doc.id,
            document_ids: [doc.id],
            doc_title: doc.title,
            review_type: reviewType,
            source: 'batch_review',
          },
        });
        const result = await agentApi.executeDecision(plan.decision_id, {
          confirmed: true,
          comment: '用户在合同助手工作台发起批量审查',
        });
        results.push(result);
        setActiveDocument(doc);
        setChunks(fullChunks);
        setCurrentPlan(normalizePlan(result.plan) || plan);
        setExecution(result);
      }
      addMessage('assistant', `批量审查完成，共处理 ${results.length} 份合同。`);
      await refreshHistory();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '批量审查失败';
      setError(msg);
      message.error(msg);
    } finally {
      setBusy(false);
      setBusyLabel('');
    }
  };

  const loadHistory = async (row: AgentExecution) => {
    const id = row.execution_id || row.id;
    if (!id) return;
    const detail = await agentApi.getExecution(id);
    setExecution(detail);
    setCurrentPlan(normalizePlan(detail.plan));
    setFeedbackScore(detail.user_feedback || 0);
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
    const result = (await agentApi.submitFeedback(id, feedbackScore, feedbackComment)) as {
      regression_case_id?: string;
    };
    setExecution((item) =>
      item ? { ...item, user_feedback: feedbackScore, regression_case_id: result.regression_case_id } : item,
    );
    message.success(result.regression_case_id ? `反馈已提交，回归样例 ${result.regression_case_id}` : '反馈已提交');
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
    link.download = `${activeDocument?.title || 'contract-review'}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const downloadExport = async (format: 'docx' | 'pdf') => {
    const id = execution?.execution_id || execution?.id;
    if (!id) return;
    const blob = await agentApi.exportExecution(id, format);
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement('a');
    link.href = url;
    link.download = `${activeDocument?.title || 'contract-review'}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const renderPlanStep = (step: PlanStep) => (
    <List.Item>
      <List.Item.Meta
        title={
          <Space wrap>
            <Text strong>{step.title}</Text>
            <Tag>{step.domain}</Tag>
            <Tag color={step.mutates_state ? 'orange' : 'blue'}>{step.tool}</Tag>
          </Space>
        }
        description={step.description}
      />
    </List.Item>
  );

  const renderPlan = (plan: AgentPlan, compact = false) => (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={plan.intent_summary}
        description={`Decision ID：${plan.decision_id}`}
      />
      <List size="small" dataSource={plan.steps} renderItem={renderPlanStep} />
      {!compact ? (
        <Space direction="vertical" size={4}>
          <Text strong>预计写入</Text>
          {plan.estimated_changes.map((item) => (
            <Text key={item} type="secondary">
              {item}
            </Text>
          ))}
        </Space>
      ) : null}
      {!compact ? (
        <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => confirmPlan(plan)} loading={busy}>
          确认并执行
        </Button>
      ) : null}
    </Space>
  );

  const renderRisk = (item: ReviewRiskItem, index: number) => {
    const uncertain = item.severity === 'uncertain' || !item.references?.some((ref) => ref.citation_id);
    return (
      <div key={`${item.issue}-${index}`} className="risk-item">
        <Space style={{ marginBottom: 8 }} wrap>
          <Tag color={severityColor[item.severity] || 'blue'}>{riskText(item.severity)}</Tag>
          {uncertain ? <Tag>依据不足</Tag> : null}
          <Text type="secondary">置信度 {Math.round((item.confidence || 0) * 100)}%</Text>
        </Space>
        <Paragraph>
          <Text strong>{item.issue}</Text>
        </Paragraph>
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
      <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
        <div>
          <Title level={4} style={{ margin: 0 }}>
            合同合规助手
          </Title>
          <Text type="secondary">自然语言输入、计划确认、跨域检索、审查报告和反馈回归闭环</Text>
        </div>
        <Button icon={<FileSearchOutlined />} onClick={refreshHistory}>
          刷新历史
        </Button>
      </Space>

      {error ? <Alert type="error" message={error} showIcon /> : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <div className="panel-block">
            <Title level={5}>合同与审查范围</Title>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Input placeholder="合同标题" value={title} onChange={(e) => setTitle(e.target.value)} />
              <Select value={reviewType} options={REVIEW_TYPES} onChange={setReviewType} />
              <Upload.Dragger
                accept=".pdf,.doc,.docx,.txt,.md"
                multiple
                maxCount={10}
                fileList={fileList}
                beforeUpload={(file) => {
                  setFileList((items) => [...items.filter((item) => item.uid !== file.uid), file]);
                  setTitle((value) => value || file.name);
                  setActiveDocument(null);
                  setChunks([]);
                  setJob(null);
                  setCurrentPlan(null);
                  setExecution(null);
                  return false;
                }}
                onRemove={(file) => {
                  setFileList((items) => items.filter((item) => item.uid !== file.uid));
                  setActiveDocument(null);
                  setChunks([]);
                }}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">拖拽或点击选择合同文件</p>
              </Upload.Dragger>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => createPlan()} loading={busy} block>
                生成审查计划
              </Button>
              <Button icon={<PlayCircleOutlined />} onClick={runBatchReview} loading={busy} block>
                批量审查
              </Button>
            </Space>
          </div>

          <div className="panel-block">
            <Title level={5}>入库状态</Title>
            {job ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Progress percent={jobPercent(job)} status={job.status === 'failed' ? 'exception' : undefined} />
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="状态">{job.status}</Descriptions.Item>
                  <Descriptions.Item label="阶段">{job.stage}</Descriptions.Item>
                  <Descriptions.Item label="文件">{job.file_name}</Descriptions.Item>
                  {activeDocument ? <Descriptions.Item label="文档 ID">{activeDocument.id}</Descriptions.Item> : null}
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

        <Col xs={24} xl={8}>
          <div className="panel-block" style={{ minHeight: 520 }}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Title level={5} style={{ margin: 0 }}>
                对话
              </Title>
              <div style={{ height: 360, overflow: 'auto', paddingRight: 4 }}>
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {chatMessages.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        background: item.role === 'user' ? '#eef6ff' : '#fafafa',
                        border: '1px solid #f0f0f0',
                      }}
                    >
                      <Text strong>{item.role === 'user' ? '你' : '合同助手'}</Text>
                      <Paragraph style={{ marginBottom: item.plan ? 12 : 0 }}>{item.content}</Paragraph>
                      {item.plan ? renderPlan(item.plan, true) : null}
                    </div>
                  ))}
                  {busy ? (
                    <Space>
                      <Spin size="small" />
                      <Text type="secondary">{busyLabel || '处理中'}</Text>
                    </Space>
                  ) : null}
                </Space>
              </div>
              <TextArea
                rows={4}
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="例如：帮我审这份采购合同，重点看付款、违约、解除，并生成修改稿"
                onPressEnter={(event) => {
                  if (!event.shiftKey) {
                    event.preventDefault();
                    createPlan();
                  }
                }}
              />
              <Button type="primary" icon={<SendOutlined />} onClick={() => createPlan()} loading={busy}>
                发送
              </Button>
            </Space>
          </div>
        </Col>

        <Col xs={24} xl={8}>
          <div className="panel-block">
            <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
              <Title level={5} style={{ margin: 0 }}>
                计划与执行
              </Title>
              {execution?.decision_id ? <Tag color="blue">{execution.decision_id}</Tag> : null}
            </Space>
            {currentPlan ? renderPlan(currentPlan) : <Empty description="发送需求后生成可确认计划" />}
          </div>

          <div className="panel-block">
            <Title level={5}>工具轨迹</Title>
            {execution?.tool_results?.length ? (
              <Timeline
                items={execution.tool_results.map((item, index) => ({
                  color: item.status === 'failed' ? 'red' : 'green',
                  children: (
                    <Space direction="vertical" size={2}>
                      <Text strong>{item.tool_name || `步骤 ${index + 1}`}</Text>
                      <Text type="secondary">
                        {Math.round(item.latency_ms || 0)} ms · {item.tokens_used || 0} tokens
                      </Text>
                      {item.span_id ? <Text type="secondary">Span：{item.span_id}</Text> : null}
                      {item.observation ? <Text>{item.observation}</Text> : null}
                    </Space>
                  ),
                }))}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="执行后显示工具调用结果" />
            )}
          </div>
        </Col>
      </Row>

      <div className="panel-block">
        <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }} align="start">
          <div>
            <Title level={5} style={{ margin: 0 }}>
              审查报告
            </Title>
            <Text type="secondary">风险条目无 citation 时会按“不确定/依据不足”展示</Text>
          </div>
          <Space>
            <Button icon={<CopyOutlined />} disabled={!execution?.result} onClick={copyMarkdown}>
              复制
            </Button>
            <Button icon={<DownloadOutlined />} disabled={!execution?.result} onClick={downloadMarkdown}>
              下载 Markdown
            </Button>
            <Button icon={<DownloadOutlined />} disabled={!execution?.result} onClick={() => downloadExport('docx')}>
              下载 DOCX
            </Button>
            <Button icon={<DownloadOutlined />} disabled={!execution?.result} onClick={() => downloadExport('pdf')}>
              下载 PDF
            </Button>
          </Space>
        </Space>

        {!execution ? (
          <Empty description="确认计划并完成审查后在这里查看风险清单" />
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
                      {chunks.slice(0, 8).map((chunk) => (
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
                placeholder="补充期望修正，提交后会生成回归样例"
                value={feedbackComment}
                onChange={(event) => setFeedbackComment(event.target.value)}
              />
              <Space>
                <Button onClick={submitFeedback}>提交反馈</Button>
                {execution.regression_case_id ? <Tag color="purple">{execution.regression_case_id}</Tag> : null}
              </Space>
            </Space>
          </Space>
        )}
      </div>

      <div className="panel-block">
        <Title level={5}>最近审查</Title>
        <Table
          rowKey={(row) => row.execution_id || row.trace_id}
          size="small"
          dataSource={history}
          pagination={false}
          onRow={(row) => ({ onClick: () => loadHistory(row) })}
          columns={[
            { title: 'Decision ID', dataIndex: 'decision_id', ellipsis: true, render: (value?: string) => value || '-' },
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
