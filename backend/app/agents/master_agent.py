"""
主Agent(调度中枢) - 任务拆解、子Agent调度、结果整合
"""

from app.agents.base import BaseAgent, Tool


class RetrievalTool(Tool):
    """检索工具"""
    name = "search_knowledge_base"
    description = "在法律知识库中检索相关法条、合同条款、合规规范。输入查询文本，返回相关文档片段。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询"},
                "doc_type": {"type": "string", "enum": ["law", "contract", "regulation", "case", "all"], "description": "文档类型过滤"},
                "top_k": {"type": "integer", "description": "返回结果数量", "default": 10},
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", doc_type: str = "all", top_k: int = 10, **kwargs) -> str:
        from app.rag.retriever import hybrid_retriever
        results = await hybrid_retriever.retrieve(query, tenant_id="default", top_k=top_k)
        if not results:
            return "未找到相关内容"
        return "\n\n".join(f"[结果{i+1}] {r.content[:500]}" for i, r in enumerate(results))


class ComplianceCheckTool(Tool):
    """合规校验工具"""
    name = "compliance_check"
    description = "对合同条款或法律文本进行合规性检查，识别潜在风险点。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "待检查的文本内容"},
                "check_type": {"type": "string", "enum": ["full", "clause", "risk"], "description": "检查类型"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str = "", check_type: str = "full", **kwargs) -> str:
        from app.services.llm_service import llm_service
        messages = [
            {"role": "system", "content": (
                "你是合同合规审查专家。请对以下内容进行合规性审查，识别风险点并给出修改建议。"
                "输出格式：\n1. 风险等级(高/中/低)\n2. 风险描述\n3. 法律依据\n4. 修改建议"
            )},
            {"role": "user", "content": text[:4000]},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class ContractComparisonTool(Tool):
    """合同条款比对工具"""
    name = "compare_clauses"
    description = "比对两个合同版本或条款之间的差异，识别变更点和潜在冲突。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text_a": {"type": "string", "description": "文本A(原版)"},
                "text_b": {"type": "string", "description": "文本B(新版)"},
            },
            "required": ["text_a", "text_b"],
        }

    async def execute(self, text_a: str = "", text_b: str = "", **kwargs) -> str:
        from app.services.llm_service import llm_service
        messages = [
            {"role": "system", "content": (
                "你是合同条款比对专家。请详细比对以下两个版本的差异，"
                "包括：新增内容、删除内容、修改内容、潜在冲突点。"
            )},
            {"role": "user", "content": f"=== 版本A ===\n{text_a[:3000]}\n\n=== 版本B ===\n{text_b[:3000]}"},
        ]
        result = await llm_service.generate(messages)
        return result["content"]


class LegalCalculationTool(Tool):
    """法律计算工具"""
    name = "legal_calculation"
    description = "进行法律相关的计算，如违约金计算、诉讼时效计算、利息计算等。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "calculation_type": {"type": "string", "description": "计算类型"},
                "parameters": {"type": "object", "description": "计算参数"},
            },
            "required": ["calculation_type"],
        }

    async def execute(self, calculation_type: str = "", parameters: dict = None, **kwargs) -> str:
        from app.services.llm_service import llm_service
        messages = [
            {"role": "system", "content": "你是法律计算专家。请根据输入参数进行精确计算，给出计算过程和结果。"},
            {"role": "user", "content": f"计算类型: {calculation_type}\n参数: {parameters}"},
        ]
        result = await llm_service.light_generate(messages)
        return result["content"]


class MasterAgent(BaseAgent):
    """主Agent - 调度中枢"""

    agent_type = "master"
    description = "合同合规Agent系统主调度器，负责理解用户意图、拆解任务、调度工具、整合结果"

    def __init__(self):
        super().__init__()
        self.register_tool(RetrievalTool())
        self.register_tool(ComplianceCheckTool())
        self.register_tool(ContractComparisonTool())
        self.register_tool(LegalCalculationTool())

    def _build_system_prompt(self) -> str:
        return """你是一位资深合同合规法律专家Agent，服务于合同合规智能审查系统。

## 核心规则（必须严格遵守）

1. **零幻觉原则**：所有生成内容必须100%基于检索上下文，禁止使用模型自身参数知识，禁止编造法条、合同条款、法律意见
2. **引用溯源**：所有观点必须标注引用来源，格式为「依据《XX》第X条：xxx」
3. **风险提示**：明确区分强制性规定与任意性规定，高亮风险点与法律后果
4. **不确定声明**：不确定的内容必须明确说明「暂无相关有效法律依据，建议咨询专业律师」

## 工作流程

1. 分析用户需求，识别任务类型（合同审查/合规校验/条款比对/法律检索/合同起草）
2. 使用search_knowledge_base工具检索相关法律法规和合同条款
3. 根据检索结果进行分析和推理
4. 如需合规检查，使用compliance_check工具
5. 如需条款比对，使用compare_clauses工具
6. 整合所有信息，生成专业、准确、有引用的回复

## 输出格式

- 使用结构化的Markdown格式
- 风险点用 ⚠️ 标注
- 法律依据用引用块标注
- 修改建议用有序列表
- 结论用加粗强调
"""


master_agent = MasterAgent()
