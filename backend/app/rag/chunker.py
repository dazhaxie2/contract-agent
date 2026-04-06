"""
文档分块引擎 - 混合分块策略
结构原子分块 + 层级父子分块 + 语义分块 + 增强摘要分块
"""

import re
import uuid
from typing import Optional

from app.core.config import settings


class ChunkResult:
    def __init__(self, content: str, chunk_type: str, hierarchy_path: str = "",
                 hierarchy_level: int = 0, parent_id: str | None = None,
                 summary: str = "", metadata: dict | None = None):
        self.id = str(uuid.uuid4())
        self.content = content
        self.chunk_type = chunk_type
        self.hierarchy_path = hierarchy_path
        self.hierarchy_level = hierarchy_level
        self.parent_id = parent_id
        self.summary = summary
        self.metadata = metadata or {}
        self.token_count = len(content)  # 简化：字符数近似


class DocumentChunker:
    """混合分块器"""

    # 法律条文结构模式
    STRUCTURE_PATTERNS = {
        "part": re.compile(r'^第[一二三四五六七八九十百千]+编\s'),
        "chapter": re.compile(r'^第[一二三四五六七八九十百千]+章\s'),
        "section": re.compile(r'^第[一二三四五六七八九十百千]+节\s'),
        "article": re.compile(r'^第[一二三四五六七八九十百千万]+条[\s　]'),
        "paragraph": re.compile(r'^（[一二三四五六七八九十]+）'),
        "item": re.compile(r'^\d+[.、]\s'),
    }

    LEVEL_MAP = {"part": 1, "chapter": 2, "section": 3, "article": 4, "paragraph": 5, "item": 6}

    def chunk(self, text: str, doc_type: str = "law", sections: list | None = None) -> list[ChunkResult]:
        """主入口：根据文档类型选择分块策略"""
        if doc_type in ("law", "regulation"):
            return self._structural_chunk(text)
        elif doc_type == "contract":
            return self._contract_chunk(text)
        else:
            return self._semantic_chunk(text)

    def _structural_chunk(self, text: str) -> list[ChunkResult]:
        """结构化分块 - 适用于法律法规"""
        chunks = []
        lines = text.split('\n')
        current_chunk_lines = []
        current_type = "content"
        current_path_stack = []  # [(level, name)]

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                if current_chunk_lines:
                    current_chunk_lines.append("")
                continue

            detected_type = self._detect_structure_type(line_stripped)

            if detected_type and detected_type != "item":
                # 保存当前块
                if current_chunk_lines:
                    chunk_text = '\n'.join(current_chunk_lines).strip()
                    if chunk_text:
                        chunks.append(self._create_chunk(
                            chunk_text, current_type, current_path_stack
                        ))
                    current_chunk_lines = []

                # 更新层级栈
                level = self.LEVEL_MAP.get(detected_type, 0)
                while current_path_stack and current_path_stack[-1][0] >= level:
                    current_path_stack.pop()
                current_path_stack.append((level, line_stripped[:20]))
                current_type = detected_type

            current_chunk_lines.append(line)

        # 最后一个块
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines).strip()
            if chunk_text:
                chunks.append(self._create_chunk(chunk_text, current_type, current_path_stack))

        # 对过大的块做拆分
        final_chunks = []
        for chunk in chunks:
            if chunk.token_count > settings.rag.chunk_size_max:
                final_chunks.extend(self._split_large_chunk(chunk))
            else:
                final_chunks.append(chunk)

        # 构建父子关系
        self._build_hierarchy(final_chunks)

        return final_chunks

    def _contract_chunk(self, text: str) -> list[ChunkResult]:
        """合同分块 - 按条款分割"""
        chunks = []

        # 合同常见结构模式
        patterns = [
            re.compile(r'^(?:第[一二三四五六七八九十百千]+条|第\d+条|[\d.]+)\s', re.MULTILINE),
            re.compile(r'^(?:甲方|乙方|丙方|丁方)[:：]', re.MULTILINE),
        ]

        # 先尝试按条款分割
        article_pattern = re.compile(
            r'(第[一二三四五六七八九十百千万]+条[^\n]*(?:\n(?!第[一二三四五六七八九十百千万]+条)[^\n]*)*)',
            re.MULTILINE
        )
        matches = list(article_pattern.finditer(text))

        if matches:
            # 前言部分
            if matches[0].start() > 50:
                preamble = text[:matches[0].start()].strip()
                if preamble:
                    chunks.append(ChunkResult(
                        content=preamble, chunk_type="structural",
                        hierarchy_path="合同前言", hierarchy_level=1,
                    ))

            for match in matches:
                content = match.group(1).strip()
                if content:
                    chunks.append(ChunkResult(
                        content=content, chunk_type="structural",
                        hierarchy_path=content[:20], hierarchy_level=4,
                    ))

            # 尾部
            if matches and matches[-1].end() < len(text) - 50:
                tail = text[matches[-1].end():].strip()
                if tail:
                    chunks.append(ChunkResult(
                        content=tail, chunk_type="structural",
                        hierarchy_path="合同尾部", hierarchy_level=1,
                    ))
        else:
            chunks = self._semantic_chunk(text)

        return chunks

    def _semantic_chunk(self, text: str) -> list[ChunkResult]:
        """语义分块 - 适用于无明确结构的文档"""
        chunks = []
        min_size = settings.rag.chunk_size_min
        max_size = settings.rag.chunk_size_max
        overlap = settings.rag.chunk_overlap

        paragraphs = re.split(r'\n{2,}', text)
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_len = len(para)

            if current_size + para_len > max_size and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append(ChunkResult(
                    content=chunk_text, chunk_type="semantic",
                    hierarchy_level=0,
                ))
                # 保留重叠
                overlap_text = current_chunk[-1] if current_chunk else ""
                current_chunk = [overlap_text] if len(overlap_text) <= overlap else []
                current_size = len(overlap_text) if current_chunk else 0

            current_chunk.append(para)
            current_size += para_len

        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            if len(chunk_text) >= min_size:
                chunks.append(ChunkResult(
                    content=chunk_text, chunk_type="semantic",
                    hierarchy_level=0,
                ))

        return chunks

    def _detect_structure_type(self, line: str) -> str | None:
        for stype, pattern in self.STRUCTURE_PATTERNS.items():
            if pattern.match(line):
                return stype
        return None

    def _create_chunk(self, text: str, chunk_type: str, path_stack: list) -> ChunkResult:
        path = " > ".join(name for _, name in path_stack)
        level = path_stack[-1][0] if path_stack else 0
        return ChunkResult(
            content=text,
            chunk_type="structural",
            hierarchy_path=path,
            hierarchy_level=level,
        )

    def _split_large_chunk(self, chunk: ChunkResult) -> list[ChunkResult]:
        """拆分过大的块"""
        text = chunk.content
        max_size = settings.rag.chunk_size_max
        sub_chunks = []

        sentences = re.split(r'([。；;！？!?])', text)
        current = []
        current_len = 0

        for i in range(0, len(sentences), 2):
            sent = sentences[i]
            if i + 1 < len(sentences):
                sent += sentences[i + 1]

            if current_len + len(sent) > max_size and current:
                sub_chunks.append(ChunkResult(
                    content=''.join(current),
                    chunk_type=chunk.chunk_type,
                    hierarchy_path=chunk.hierarchy_path,
                    hierarchy_level=chunk.hierarchy_level,
                    parent_id=chunk.id,
                ))
                current = []
                current_len = 0

            current.append(sent)
            current_len += len(sent)

        if current:
            sub_chunks.append(ChunkResult(
                content=''.join(current),
                chunk_type=chunk.chunk_type,
                hierarchy_path=chunk.hierarchy_path,
                hierarchy_level=chunk.hierarchy_level,
                parent_id=chunk.id,
            ))

        return sub_chunks if sub_chunks else [chunk]

    def _build_hierarchy(self, chunks: list[ChunkResult]):
        """构建父子层级关系"""
        parent_stack: list[ChunkResult] = []

        for chunk in chunks:
            while parent_stack and parent_stack[-1].hierarchy_level >= chunk.hierarchy_level:
                parent_stack.pop()

            if parent_stack:
                chunk.parent_id = parent_stack[-1].id

            parent_stack.append(chunk)


document_chunker = DocumentChunker()
