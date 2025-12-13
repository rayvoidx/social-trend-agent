"""
Common RAG Module
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import re

from src.core.config import get_config_manager, ConfigManager
from src.integrations.llm.llm_client import get_llm_client
from src.integrations.retrieval.vectorstore_pinecone import PineconeVectorStore

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣#@]{2,}")


def _extract_entities(text: str, max_entities: int = 20) -> List[str]:
    """
    Heuristic entity extraction for GraphRAG-style rerank.
    - Works for both Korean and English without extra deps.
    """
    if not text:
        return []
    toks = _TOKEN_RE.findall(text)
    # Dedup while keeping order
    seen = set()
    out: List[str] = []
    for t in toks:
        tt = t.strip()
        if not tt:
            continue
        key = tt.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tt[:60])
        if len(out) >= max_entities:
            break
    return out


def _graph_score(query_entities: List[str], meta: Dict[str, Any]) -> float:
    """
    Graph score = overlap between query entities and metadata.entities/tags.
    Returns a small float (0..1-ish).
    """
    if not query_entities or not isinstance(meta, dict):
        return 0.0
    meta_ents = meta.get("entities")
    if isinstance(meta_ents, list):
        meta_set = {str(x).lower() for x in meta_ents if isinstance(x, str)}
    else:
        meta_set = set()
    overlap = sum(1 for qe in query_entities if qe.lower() in meta_set)
    return min(1.0, overlap / max(1, len(query_entities)))


def _rerank_hybrid(
    matches: List[Dict[str, Any]],
    query: str,
    alpha: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    Hybrid rerank:
    final = vector_score + alpha * graph_score
    """
    qents = _extract_entities(query)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for m in matches:
        try:
            v = float(m.get("score", 0.0))
        except Exception:
            v = 0.0
        meta = m.get("metadata") or {}
        g = _graph_score(qents, meta)
        scored.append((v + alpha * g, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]


class RAGSystem:
    """
    설정 기반 RAG 시스템
    
    에이전트별 설정을 읽어 적절한 벡터 저장소와 임베딩 모델을 사용합니다.
    """

    def __init__(self, agent_name: str, config_manager: Optional[ConfigManager] = None):
        self.agent_name = agent_name
        self.cfg = config_manager or get_config_manager()
        self.agent_cfg = self.cfg.get_agent_config(agent_name)
        
        self.vector_store = None
        self.llm_client = get_llm_client()
        self.enabled = False
        
        self._initialize()

    def _initialize(self):
        """설정을 기반으로 벡터 스토어 초기화"""
        if not self.agent_cfg:
            logger.warning(f"No configuration found for agent: {self.agent_name}")
            return

        vs_cfg = self.agent_cfg.vector_store or {}
        vs_type = vs_cfg.get("type")
        
        if vs_type == "pinecone":
            index_name = vs_cfg.get("index_name")
            if not index_name:
                logger.warning(f"Pinecone index name missing for {self.agent_name}")
                return
                
            try:
                # 네임스페이스는 에이전트 이름을 기본값으로 사용
                namespace = vs_cfg.get("namespace", self.agent_name)
                
                self.vector_store = PineconeVectorStore(
                    index_name=index_name,
                    namespace=namespace
                )
                self.enabled = True
                logger.info(f"RAG initialized for {self.agent_name}: Pinecone(index={index_name}, ns={namespace})")
            except Exception as e:
                logger.error(f"Failed to initialize Pinecone for {self.agent_name}: {e}")
        else:
            if vs_type:
                logger.warning(f"Unsupported vector store type: {vs_type} for {self.agent_name}")

    def index_documents(self, documents: List[str], metadatas: List[Dict[str, Any]]) -> int:
        """
        문서를 임베딩하여 벡터 스토어에 저장
        
        Args:
            documents: 텍스트 리스트
            metadatas: 메타데이터 리스트
            
        Returns:
            저장된 문서 수
        """
        if not self.enabled or not self.vector_store:
            return 0
            
        try:
            # Generate IDs
            ids = [self._generate_id(doc) for doc in documents]
            
            # Get embeddings
            embeddings = self.llm_client.get_embeddings_batch(documents)
            
            # GraphRAG simulation: add lightweight entities to metadata (Pinecone supports list[str])
            enriched: List[Dict[str, Any]] = []
            for doc, meta in zip(documents, metadatas):
                m = dict(meta or {})
                # Try to include title/content for better entity extraction if present
                title = str(m.get("title", "") or "")
                content = str(m.get("content", "") or "")
                ents = _extract_entities(" ".join([title, content, doc]))
                if ents:
                    m["entities"] = ents
                enriched.append(m)

            # Upsert
            count = self.vector_store.upsert(ids, embeddings, enriched)
            return count
        except Exception as e:
            logger.error(f"Indexing failed for {self.agent_name}: {e}")
            return 0

    def retrieve(self, query: str, top_k: int = 10, use_graph: bool = True) -> List[Dict[str, Any]]:
        """
        쿼리와 관련된 문서 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            
        Returns:
            검색된 문서의 메타데이터 리스트
        """
        if not self.enabled or not self.vector_store:
            return []
            
        try:
            # Get query embedding
            query_vector = self.llm_client.get_embedding(query)
            
            # Search (get a wider pool for rerank)
            pool_k = max(top_k, min(50, top_k * 3))
            matches = self.vector_store.query(query_vector, top_k=pool_k)

            if use_graph:
                matches = _rerank_hybrid(matches, query=query)

            return [m.get("metadata") or {} for m in matches[:top_k]]
        except Exception as e:
            logger.error(f"Retrieval failed for {self.agent_name}: {e}")
            return []

    def _generate_id(self, content: str) -> str:
        """콘텐츠 기반 ID 생성"""
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def is_enabled(self) -> bool:
        return self.enabled

