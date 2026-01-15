"""
RAG Retriever - SOP 文档知识检索器

使用 ChromaDB 向量数据库存储和检索 CATIA 操作 SOP 文档。
支持 Markdown 文档分块、向量检索和上下文格式化。

Author: CATIA VLA Team
"""

import os
import re
import json
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """文档块数据类"""
    id: str
    content: str
    metadata: Dict[str, Any]
    source_file: str
    section_title: str


@dataclass
class RetrievalResult:
    """检索结果数据类"""
    content: str
    score: float
    metadata: Dict[str, Any]
    source: str


class SOPRetriever:
    """
    SOP 文档 RAG 检索器
    
    功能：
    1. 索引 Markdown SOP 文档
    2. 向量相似度检索
    3. 格式化检索结果为 Prompt 上下文
    
    Usage:
        retriever = SOPRetriever()
        retriever.index_documents("./knowledge/sop_docs")
        results = retriever.search("创建加强筋", top_k=3)
        context = retriever.format_context(results)
    """
    
    def __init__(
        self,
        persist_dir: str = "./cache_dir/chroma_db",
        collection_name: str = "catia_sop",
        embedding_model: str = "default",
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        """
        初始化检索器
        
        Args:
            persist_dir: ChromaDB 持久化目录
            collection_name: 集合名称
            embedding_model: 嵌入模型名称
            chunk_size: 分块大小（字符数）
            chunk_overlap: 分块重叠（字符数）
        """
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        self._client = None
        self._collection = None
        self._initialized = False
        
    def _ensure_initialized(self):
        """确保 ChromaDB 已初始化"""
        if self._initialized:
            return
            
        try:
            import chromadb
            from chromadb.config import Settings
            
            # 确保目录存在
            os.makedirs(self.persist_dir, exist_ok=True)
            
            # 创建客户端
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 获取或创建集合
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            self._initialized = True
            logger.info(f"ChromaDB 初始化完成: {self.persist_dir}")
            
        except ImportError:
            logger.warning("chromadb 未安装，使用内存模式")
            self._use_memory_mode()
        except Exception as e:
            logger.warning(f"ChromaDB 初始化失败，使用内存模式: {e}")
            self._use_memory_mode()
    
    def _use_memory_mode(self):
        """使用内存模式（当 ChromaDB 不可用时）"""
        self._memory_store: List[DocumentChunk] = []
        self._initialized = True
        logger.info("使用内存模式存储文档")
    
    def index_documents(self, docs_dir: str) -> int:
        """
        索引 SOP 文档目录
        
        Args:
            docs_dir: 文档目录路径
            
        Returns:
            索引的文档块数量
        """
        self._ensure_initialized()
        
        docs_path = Path(docs_dir)
        if not docs_path.exists():
            logger.warning(f"文档目录不存在: {docs_dir}")
            return 0
        
        # 查找所有 Markdown 文件
        md_files = list(docs_path.glob("**/*.md"))
        logger.info(f"找到 {len(md_files)} 个 Markdown 文件")
        
        total_chunks = 0
        
        for md_file in md_files:
            try:
                chunks = self._process_markdown_file(md_file)
                self._add_chunks(chunks)
                total_chunks += len(chunks)
                logger.info(f"处理文件: {md_file.name}, {len(chunks)} 个块")
            except Exception as e:
                logger.error(f"处理文件失败 {md_file}: {e}")
        
        logger.info(f"索引完成，共 {total_chunks} 个文档块")
        return total_chunks
    
    def _process_markdown_file(self, file_path: Path) -> List[DocumentChunk]:
        """
        处理 Markdown 文件，按标题分块
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档块列表
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        chunks = []
        
        # 按一级或二级标题分割
        sections = re.split(r'\n(?=##?\s)', content)
        
        for section in sections:
            if not section.strip():
                continue
            
            # 提取标题
            title_match = re.match(r'^(##?\s+.+?)(?:\n|$)', section)
            title = title_match.group(1).strip() if title_match else "Introduction"
            
            # 如果块太大，进一步分割
            if len(section) > self.chunk_size:
                sub_chunks = self._split_large_section(section, title)
                chunks.extend(sub_chunks)
            else:
                chunk_id = self._generate_chunk_id(file_path.name, title)
                chunks.append(DocumentChunk(
                    id=chunk_id,
                    content=section.strip(),
                    metadata={
                        "source": file_path.name,
                        "title": title,
                        "char_count": len(section)
                    },
                    source_file=str(file_path),
                    section_title=title
                ))
        
        return chunks
    
    def _split_large_section(
        self, 
        content: str, 
        base_title: str
    ) -> List[DocumentChunk]:
        """分割大块内容"""
        chunks = []
        
        # 按段落分割
        paragraphs = content.split('\n\n')
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip():
                    chunk_id = self._generate_chunk_id(
                        base_title, f"part_{chunk_index}"
                    )
                    chunks.append(DocumentChunk(
                        id=chunk_id,
                        content=current_chunk.strip(),
                        metadata={
                            "title": f"{base_title} (Part {chunk_index + 1})",
                            "char_count": len(current_chunk)
                        },
                        source_file="",
                        section_title=base_title
                    ))
                    chunk_index += 1
                current_chunk = para + "\n\n"
        
        # 处理最后一块
        if current_chunk.strip():
            chunk_id = self._generate_chunk_id(base_title, f"part_{chunk_index}")
            chunks.append(DocumentChunk(
                id=chunk_id,
                content=current_chunk.strip(),
                metadata={
                    "title": f"{base_title} (Part {chunk_index + 1})",
                    "char_count": len(current_chunk)
                },
                source_file="",
                section_title=base_title
            ))
        
        return chunks
    
    def _generate_chunk_id(self, *args) -> str:
        """生成块 ID"""
        text = "_".join(str(a) for a in args)
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def _add_chunks(self, chunks: List[DocumentChunk]):
        """添加块到存储"""
        if self._collection is not None:
            # ChromaDB 模式
            ids = [c.id for c in chunks]
            documents = [c.content for c in chunks]
            metadatas = [c.metadata for c in chunks]
            
            self._collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
        else:
            # 内存模式
            self._memory_store.extend(chunks)
    
    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.0
    ) -> List[RetrievalResult]:
        """
        检索相关 SOP 片段
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            min_score: 最小相似度阈值
            
        Returns:
            检索结果列表
        """
        self._ensure_initialized()
        
        if self._collection is not None:
            # ChromaDB 检索
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=top_k
                )
                
                retrieval_results = []
                
                if results and results['documents']:
                    for i, doc in enumerate(results['documents'][0]):
                        # ChromaDB 返回距离，转换为相似度
                        distance = results['distances'][0][i] if results['distances'] else 0
                        score = 1.0 - distance  # cosine 距离转相似度
                        
                        if score >= min_score:
                            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                            retrieval_results.append(RetrievalResult(
                                content=doc,
                                score=score,
                                metadata=metadata,
                                source=metadata.get('source', 'unknown')
                            ))
                
                return retrieval_results
                
            except Exception as e:
                logger.error(f"ChromaDB 检索失败: {e}")
                return []
        else:
            # 内存模式：简单关键词匹配
            return self._memory_search(query, top_k, min_score)
    
    def _memory_search(
        self,
        query: str,
        top_k: int,
        min_score: float
    ) -> List[RetrievalResult]:
        """内存模式的简单搜索"""
        results = []
        query_lower = query.lower()
        query_keywords = set(query_lower.split())
        
        for chunk in self._memory_store:
            content_lower = chunk.content.lower()
            
            # 简单的关键词匹配评分
            matches = sum(1 for kw in query_keywords if kw in content_lower)
            score = matches / len(query_keywords) if query_keywords else 0
            
            if score >= min_score:
                results.append(RetrievalResult(
                    content=chunk.content,
                    score=score,
                    metadata=chunk.metadata,
                    source=chunk.source_file
                ))
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def format_context(
        self,
        results: List[RetrievalResult],
        max_length: int = 2000
    ) -> str:
        """
        格式化检索结果为 Prompt 上下文
        
        Args:
            results: 检索结果列表
            max_length: 最大长度（字符数）
            
        Returns:
            格式化的上下文文本
        """
        if not results:
            return ""
        
        context_parts = []
        current_length = 0
        
        for i, result in enumerate(results, 1):
            header = f"### 相关文档 {i} (相似度: {result.score:.2f})\n"
            source = f"来源: {result.source}\n" if result.source else ""
            content = result.content
            
            part = f"{header}{source}\n{content}\n\n---\n"
            
            if current_length + len(part) > max_length:
                # 截断内容
                available = max_length - current_length - len(header) - len(source) - 20
                if available > 100:
                    truncated_content = content[:available] + "...(截断)"
                    part = f"{header}{source}\n{truncated_content}\n\n---\n"
                    context_parts.append(part)
                break
            
            context_parts.append(part)
            current_length += len(part)
        
        return "\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        self._ensure_initialized()
        
        if self._collection is not None:
            count = self._collection.count()
            return {
                "mode": "chromadb",
                "collection": self.collection_name,
                "document_count": count,
                "persist_dir": self.persist_dir
            }
        else:
            return {
                "mode": "memory",
                "document_count": len(self._memory_store)
            }
    
    def clear(self):
        """清空索引"""
        self._ensure_initialized()
        
        if self._collection is not None:
            # 删除并重建集合
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        else:
            self._memory_store.clear()
        
        logger.info("索引已清空")


# ==================== 异步包装器 ====================

async def retrieve_sop_for_task(
    query: str,
    retriever: Optional[SOPRetriever] = None,
    top_k: int = 3
) -> str:
    """
    异步检索 SOP 文档
    
    Args:
        query: 查询文本
        retriever: SOPRetriever 实例（可选，会自动创建）
        top_k: 返回结果数量
        
    Returns:
        格式化的上下文文本
    """
    if retriever is None:
        retriever = SOPRetriever()
    
    results = retriever.search(query, top_k=top_k)
    return retriever.format_context(results)


# ==================== OxyGent RAGAgent 集成 ====================

def create_rag_knowledge_func(retriever: SOPRetriever):
    """
    创建用于 RAGAgent 的知识检索函数
    
    Args:
        retriever: SOPRetriever 实例
        
    Returns:
        可用于 RAGAgent 的异步检索函数
    """
    async def retrieve_knowledge(oxy_request) -> str:
        """RAGAgent 知识检索函数"""
        # 从 OxyRequest 获取查询
        query = ""
        if hasattr(oxy_request, 'get_query'):
            query = oxy_request.get_query()
        elif hasattr(oxy_request, 'messages'):
            # 获取最后一条用户消息
            for msg in reversed(oxy_request.messages):
                if msg.get('role') == 'user':
                    query = msg.get('content', '')
                    break
        
        if not query:
            return ""
        
        results = retriever.search(query, top_k=3)
        context = retriever.format_context(results)
        
        if context:
            return f"\n## 相关 SOP 文档\n\n{context}\n"
        return ""
    
    return retrieve_knowledge


# ==================== 示例 SOP 文档 ====================

SAMPLE_SOP_CONTENT = '''
# SOP: 创建带加强筋的底座

## 概述

本文档描述如何在 CATIA V5 中创建一个带有加强筋的底座结构。

## 前置条件

- CATIA V5 R21 或更高版本
- Part Design 工作台
- 已创建新的 Part 文档

## 操作步骤

### 步骤 1: 创建底板

1. 在 XY 平面创建矩形草图
2. 尺寸: 200mm x 150mm
3. 使用 Pad 命令拉伸 10mm 创建底板

**工具调用示例:**
```
create_rectangle_sketch(support_plane="PlaneXY", length=200, width=150)
create_pad(profile_name="Rect_200x150", height=10)
```

### 步骤 2: 创建加强筋

1. 在底板上表面创建新草图
2. 绘制加强筋轮廓（矩形）
3. 使用 Pad 命令创建加强筋

### 步骤 3: 添加圆角

1. 选择底板与加强筋的交接边缘
2. 添加 R5 圆角

**工具调用示例:**
```
create_fillet(first_surface="Pad_10mm", second_surface="Rib", radius=5)
```

## 注意事项

- 加强筋方向应与主要受力方向垂直
- 圆角半径不宜过大（建议 R3-R8）
- 确保草图完全约束后再进行拉伸操作

## 常见问题

Q: 为什么拉伸失败？
A: 检查草图是否封闭，是否完全约束。

Q: 如何修改已创建的特征？
A: 在特征树中双击特征进行编辑。
'''


def create_sample_sop_docs(output_dir: str = "./applications/catia_vla/knowledge/sop_docs"):
    """创建示例 SOP 文档"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 写入示例文档
    (output_path / "sop_base_with_ribs.md").write_text(SAMPLE_SOP_CONTENT, encoding="utf-8")
    
    # 创建更多示例文档
    cube_sop = '''
# SOP: 创建立方体

## 概述

创建基本的立方体几何体。

## 步骤

1. 创建新 Part 文档
2. 在 XY 平面创建正方形草图
3. 拉伸创建立方体

## 工具调用

```
create_new_part()
create_rectangle_sketch(support_plane="PlaneXY", length=100, width=100)
create_pad(profile_name="Rect_100x100", height=100)
```
'''
    (output_path / "sop_create_cube.md").write_text(cube_sop, encoding="utf-8")
    
    logger.info(f"示例 SOP 文档已创建: {output_dir}")
    return output_dir


# ==================== 使用示例 ====================

def _demo():
    """演示用法"""
    # 创建示例文档
    docs_dir = create_sample_sop_docs()
    
    # 初始化检索器
    retriever = SOPRetriever()
    
    # 索引文档
    count = retriever.index_documents(docs_dir)
    print(f"索引了 {count} 个文档块")
    
    # 检索
    results = retriever.search("创建加强筋", top_k=3)
    print(f"\n检索到 {len(results)} 个结果:")
    
    for i, r in enumerate(results, 1):
        print(f"\n--- 结果 {i} (分数: {r.score:.2f}) ---")
        print(r.content[:200] + "..." if len(r.content) > 200 else r.content)
    
    # 格式化上下文
    context = retriever.format_context(results)
    print(f"\n格式化上下文:\n{context}")
    
    # 统计
    print(f"\n索引统计: {retriever.get_stats()}")


if __name__ == "__main__":
    _demo()
