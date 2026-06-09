# 维度二：AI 质量与零幻觉保障 — 执行计划

## 现状总结

| 项目 | 当前状态 |
|------|---------|
| 评估测试集 | **10 条**（`tests/fixtures/evaluation_test_set.json`），覆盖 9 类场景 |
| JSON Schema | 完备（`evaluation_test_set.schema.json`），支持 9 category、7 agent、3 difficulty |
| 评估运行器 | `test_evaluation_suite.py` + CLI `run_evaluation.py` + CI 流水线 |
| 多模态能力 | **零** — `paddleocr` 在 requirements 但未接入，无图像/视觉代码 |
| 文档处理器 | 纯文本解析（PyMuPDF PDF + python-docx DOCX），无扫描件处理 |

---

## 任务一：法务专家评估测试集扩展（1000+ 条）

### 1.1 扩展 JSON Schema

在 `evaluation_test_set.schema.json` 中增加可选字段：
- `subcategory`: 细分场景（如 payment_terms、breach_liability）
- `contract_type`: 合同类型（如 purchase、labor、lease、nda）

### 1.2 场景覆盖规划（1000+ 条分布）

| 类别 | 条数 | 重点覆盖 |
|------|------|---------|
| `contract_review` | ~200 | 付款条款(40)、违约责任(40)、解除条款(30)、保密条款(30)、担保(30)、知识产权(30) |
| `legal_search` | ~150 | 民法典(40)、劳动合同法(30)、公司法(25)、招投标法(25)、知识产权法(30) |
| `comparison` | ~100 | 条款差异对比(50)、版本变更(30)、风险变更评估(20) |
| `drafting` | ~120 | 保密协议(25)、付款条款(25)、违约条款(20)、争议解决(20)、担保条款(30) |
| `calculation` | ~80 | 违约金计算(20)、利息计算(15)、损害赔偿(15)、定金规则(15)、时效计算(15) |
| `compliance` | ~120 | 格式条款(25)、消费者保护(20)、反垄断(20)、数据合规(25)、行业合规(30) |
| `retrieval` | ~100 | 建设工程(20)、劳动合同(20)、买卖合同(20)、租赁合同(20)、知识产权(20) |
| `validation` | ~80 | 法条引用准确性(30)、法律结论验证(30)、数字/日期验证(20) |
| `multi_step` | ~80 | 审查+起草(25)、检索+验证(20)、比对+修改(20)、全流程(15) |

### 1.3 实施步骤

1. 创建场景模板文件 `tests/fixtures/test_templates.json`
2. 创建测试用例生成脚本 `scripts/generate_test_set.py`
3. 生成 `tests/fixtures/evaluation_test_set_full.json`（1000+ 条）
4. 更新验证脚本、评估运行器、CLI、CI 流水线

---

## 任务二：多模态物理合同件解析（签名与盖章识别）

### 2.1 目标

对扫描件 PDF/照片实现：
- 手写签名自动定位
- 企业公章/合同专用章检测
- 合规性审查（是否缺少签章、签章位置是否合规）

### 2.2 架构设计

```
扫描件 PDF / 照片
     │
     ▼
┌────────────────────────────┐
│  DocumentProcessor         │
│  ├─ PyMuPDF 文本提取       │
│  ├─ [文本过少?] → PaddleOCR │
│  └─ 输出: 文本 + 页面图片   │
└──────────┬─────────────────┘
           │
           ▼
┌────────────────────────────┐
│  MultimodalService         │
│  ├─ SignatureDetector      │
│  │   ├─ OpenCV 轮廓分析    │
│  │   └─ [可选] VL模型验证   │
│  ├─ SealDetector           │
│  │   ├─ HSV 红色区域提取   │
│  │   └─ 圆形度+尺寸校验    │
│  └─ 输出: 签章报告         │
└──────────┬─────────────────┘
           │
           ▼
┌────────────────────────────┐
│  ComplianceAgent           │
│  └─ 合规性判定:            │
│     - 是否缺少签名/盖章    │
│     - 签章位置是否合规      │
│     - 是否为伪造印章(可选)  │
└────────────────────────────┘
```

### 2.3 实施步骤

1. 新增 `MultimodalSettings` 到 `config.py`
2. 创建 `multimodal_service.py` 核心服务
3. 创建 `signature_detector.py` 签名检测（OpenCV 轮廓分析 + 可选 VL 模型验证）
4. 创建 `seal_detector.py` 印章检测（HSV 红色区域提取 + 圆形度校验）
5. 更新 `document_processor.py` 增加 OCR 分支
6. 更新 `ingestion_service.py` 增加多模态分析阶段
7. 创建 multimodal API 路由 + Schema
8. 注册路由、更新 requirements.txt
9. 编写测试

### 2.4 文件变更总览

| 操作 | 文件路径 |
|------|---------|
| **新建** | `backend/scripts/generate_test_set.py` |
| **新建** | `backend/tests/fixtures/test_templates.json` |
| **新建** | `backend/tests/fixtures/evaluation_test_set_full.json` |
| **新建** | `backend/app/services/multimodal_service.py` |
| **新建** | `backend/app/services/signature_detector.py` |
| **新建** | `backend/app/services/seal_detector.py` |
| **新建** | `backend/app/api/v1/multimodal.py` |
| **新建** | `backend/app/schemas/multimodal.py` |
| **新建** | `backend/tests/test_multimodal.py` |
| **修改** | `backend/app/core/config.py` |
| **修改** | `backend/app/rag/document_processor.py` |
| **修改** | `backend/app/services/ingestion_service.py` |
| **修改** | `backend/app/api/v1/router.py` |
| **修改** | `backend/tests/fixtures/evaluation_test_set.schema.json` |
| **修改** | `backend/scripts/validate_evaluation_set.py` |
| **修改** | `backend/tests/test_evaluation_suite.py` |
| **修改** | `backend/scripts/run_evaluation.py` |
| **修改** | `.github/workflows/evaluation.yml` |
| **修改** | `backend/requirements.txt` |
| **修改** | `docs/IMPROVEMENT_PLAN.md` |
