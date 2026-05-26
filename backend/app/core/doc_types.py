"""规范文档类型常量与依据归类。

doc_type 既用于入库分类，也决定审查时引用属于"法律依据"还是"企业制度依据"。
集中在此避免散落的魔法字符串在检索、上下文构建和审查报告之间漂移。
"""

from __future__ import annotations

LAW = "law"
REGULATION = "regulation"
CONTRACT = "contract"
CASE = "case"
GUIDE = "guide"
ENTERPRISE_RULE = "enterprise_rule"  # 企业自有规章制度

KNOWN_DOC_TYPES = frozenset({LAW, REGULATION, CONTRACT, CASE, GUIDE, ENTERPRISE_RULE})

# 权威外部法律来源，用于和企业内部制度区分
LEGAL_BASIS_DOC_TYPES = frozenset({LAW, REGULATION, CASE})

BASIS_LEGAL = "legal"
BASIS_ENTERPRISE = "enterprise"
BASIS_OTHER = "other"


def basis_kind(doc_type: str | None) -> str:
    """把引用依据归类为 legal / enterprise / other，供报告分区展示。"""
    if doc_type == ENTERPRISE_RULE:
        return BASIS_ENTERPRISE
    if doc_type in LEGAL_BASIS_DOC_TYPES:
        return BASIS_LEGAL
    return BASIS_OTHER
