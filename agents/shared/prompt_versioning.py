"""
프롬프트 최적화 및 버전 관리 시스템

버전 관리 및 A/B 테스팅이 통합된 체계적인 프롬프트 엔지니어링을 지원합니다.

주요 기능:
- Git 스타일의 프롬프트 버전 관리
- LLM-as-judge를 활용한 자동화된 프롬프트 최적화
- A/B 테스팅 프레임워크와의 통합
- 프롬프트 템플릿 라이브러리
- 프롬프트 버전별 성능 추적

LangChain 프롬프트 엔지니어링 패턴 기반:
https://python.langchain.com/docs/modules/model_io/prompts/
"""
import json
import hashlib
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class PromptType(str, Enum):
    """프롬프트 템플릿 타입"""
    CHAT = "chat"
    COMPLETION = "completion"
    FEW_SHOT = "few_shot"


class OptimizationStrategy(str, Enum):
    """프롬프트 최적화 전략"""
    MANUAL = "manual"              # 수동 편집
    LLM_JUDGE = "llm_judge"       # LLM이 평가하고 개선 제안
    AB_TEST = "ab_test"           # 다중 변형 A/B 테스트
    GENETIC = "genetic"           # 유전 알고리즘 최적화


@dataclass
class PromptVersion:
    """
    프롬프트의 단일 버전

    메타데이터 및 성능 추적 정보를 포함하는 특정 버전을 나타냅니다.
    """
    version_id: str
    prompt_name: str
    prompt_type: PromptType
    template: str
    variables: List[str]

    # Metadata
    created_at: float
    created_by: str
    description: str
    tags: List[str] = field(default_factory=list)

    # Performance tracking
    usage_count: int = 0
    avg_quality_score: float = 0.0
    avg_execution_time: float = 0.0

    # Parent version (for tracking evolution)
    parent_version_id: Optional[str] = None
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.MANUAL

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['prompt_type'] = self.prompt_type.value
        data['optimization_strategy'] = self.optimization_strategy.value
        return data

    def get_hash(self) -> str:
        """중복 제거를 위한 컨텐츠 해시 반환"""
        content = f"{self.prompt_name}:{self.template}:{','.join(self.variables)}"
        return hashlib.sha256(content.encode()).hexdigest()[:8]


@dataclass
class PromptPerformance:
    """프롬프트 버전의 성능 메트릭"""
    version_id: str
    timestamp: float
    query: str
    quality_score: float
    execution_time: float
    tokens_used: int
    cost_usd: float
    success: bool
    error: Optional[str] = None


class PromptLibrary:
    """
    버전 관리가 가능한 프롬프트 템플릿 라이브러리

    Git과 유사한 버전 관리 방식으로 프롬프트 템플릿을 관리합니다.

    Example:
        ```python
        library = PromptLibrary()

        # 새 프롬프트 등록
        version = library.register_prompt(
            prompt_name="trend_summarizer",
            template="Analyze these trends: {data}",
            variables=["data"],
            description="Summarizes consumer trends"
        )

        # 최신 버전 조회
        latest = library.get_latest_version("trend_summarizer")

        # 새 버전 생성
        v2 = library.create_version(
            prompt_name="trend_summarizer",
            template="Deeply analyze these trends: {data}\\nFocus on: {focus}",
            variables=["data", "focus"],
            parent_version_id=latest.version_id
        )
        ```
    """

    def __init__(self, storage_dir: str = "artifacts/prompts"):
        """
        프롬프트 라이브러리 초기화

        Args:
            storage_dir: 프롬프트 버전을 저장할 디렉토리
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory index: {prompt_name: [versions]}
        self.prompts: Dict[str, List[PromptVersion]] = {}

        # Performance history
        self.performance_history: List[PromptPerformance] = []

        # Load existing prompts
        self._load_prompts()

    def _load_prompts(self):
        """Load prompts from disk"""
        if not self.storage_dir.exists():
            return

        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath) as f:
                    data = json.load(f)

                version = PromptVersion(
                    version_id=data["version_id"],
                    prompt_name=data["prompt_name"],
                    prompt_type=PromptType(data["prompt_type"]),
                    template=data["template"],
                    variables=data["variables"],
                    created_at=data["created_at"],
                    created_by=data["created_by"],
                    description=data["description"],
                    tags=data.get("tags", []),
                    usage_count=data.get("usage_count", 0),
                    avg_quality_score=data.get("avg_quality_score", 0.0),
                    avg_execution_time=data.get("avg_execution_time", 0.0),
                    parent_version_id=data.get("parent_version_id"),
                    optimization_strategy=OptimizationStrategy(data.get("optimization_strategy", "manual"))
                )

                if version.prompt_name not in self.prompts:
                    self.prompts[version.prompt_name] = []

                self.prompts[version.prompt_name].append(version)

            except Exception as e:
                logger.warning(f"Failed to load prompt from {filepath}: {e}")

        logger.info(f"Loaded {sum(len(v) for v in self.prompts.values())} prompt versions")

    def register_prompt(
        self,
        prompt_name: str,
        template: str,
        variables: List[str],
        prompt_type: PromptType = PromptType.CHAT,
        description: str = "",
        tags: List[str] = None,
        created_by: str = "system"
    ) -> PromptVersion:
        """
        Register new prompt template

        Args:
            prompt_name: Unique name for prompt
            template: Template string
            variables: List of variable names
            prompt_type: Type of prompt
            description: Description
            tags: Tags for categorization
            created_by: Creator identifier

        Returns:
            PromptVersion
        """
        version_id = f"{prompt_name}_v{self._get_next_version_number(prompt_name)}"

        version = PromptVersion(
            version_id=version_id,
            prompt_name=prompt_name,
            prompt_type=prompt_type,
            template=template,
            variables=variables,
            created_at=datetime.now().timestamp(),
            created_by=created_by,
            description=description,
            tags=tags or []
        )

        # Store in memory
        if prompt_name not in self.prompts:
            self.prompts[prompt_name] = []

        self.prompts[prompt_name].append(version)

        # Save to disk
        self._save_version(version)

        logger.info(f"Registered prompt version: {version_id}")

        return version

    def create_version(
        self,
        prompt_name: str,
        template: str,
        variables: List[str],
        parent_version_id: Optional[str] = None,
        description: str = "",
        optimization_strategy: OptimizationStrategy = OptimizationStrategy.MANUAL
    ) -> PromptVersion:
        """
        Create new version of existing prompt

        Args:
            prompt_name: Prompt name
            template: New template
            variables: Variable names
            parent_version_id: Parent version (uses latest if None)
            description: Version description
            optimization_strategy: How this version was created

        Returns:
            PromptVersion
        """
        # Get parent if not specified
        if parent_version_id is None:
            latest = self.get_latest_version(prompt_name)
            parent_version_id = latest.version_id if latest else None

        # Get parent to copy metadata
        parent = None
        if parent_version_id:
            parent = self.get_version(parent_version_id)

        version_id = f"{prompt_name}_v{self._get_next_version_number(prompt_name)}"

        version = PromptVersion(
            version_id=version_id,
            prompt_name=prompt_name,
            prompt_type=parent.prompt_type if parent else PromptType.CHAT,
            template=template,
            variables=variables,
            created_at=datetime.now().timestamp(),
            created_by="system",
            description=description,
            tags=parent.tags if parent else [],
            parent_version_id=parent_version_id,
            optimization_strategy=optimization_strategy
        )

        self.prompts[prompt_name].append(version)
        self._save_version(version)

        logger.info(f"Created prompt version: {version_id} (parent: {parent_version_id})")

        return version

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        """Get specific version by ID"""
        for versions in self.prompts.values():
            for version in versions:
                if version.version_id == version_id:
                    return version
        return None

    def get_latest_version(self, prompt_name: str) -> Optional[PromptVersion]:
        """Get latest version of prompt"""
        versions = self.prompts.get(prompt_name, [])
        if not versions:
            return None

        # Sort by created_at descending
        sorted_versions = sorted(versions, key=lambda v: v.created_at, reverse=True)
        return sorted_versions[0]

    def get_best_version(self, prompt_name: str) -> Optional[PromptVersion]:
        """Get best performing version based on quality score"""
        versions = self.prompts.get(prompt_name, [])
        if not versions:
            return None

        # Filter versions with usage
        used_versions = [v for v in versions if v.usage_count > 0]
        if not used_versions:
            return self.get_latest_version(prompt_name)

        # Sort by quality score descending
        sorted_versions = sorted(used_versions, key=lambda v: v.avg_quality_score, reverse=True)
        return sorted_versions[0]

    def get_all_versions(self, prompt_name: str) -> List[PromptVersion]:
        """Get all versions of a prompt"""
        return self.prompts.get(prompt_name, [])

    def record_performance(
        self,
        version_id: str,
        query: str,
        quality_score: float,
        execution_time: float,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        success: bool = True,
        error: Optional[str] = None
    ):
        """
        Record performance metrics for a version

        Args:
            version_id: Version ID
            query: Query processed
            quality_score: Quality score (0.0-1.0)
            execution_time: Execution time in seconds
            tokens_used: Number of tokens
            cost_usd: Cost in USD
            success: Whether execution succeeded
            error: Error message if failed
        """
        performance = PromptPerformance(
            version_id=version_id,
            timestamp=datetime.now().timestamp(),
            query=query,
            quality_score=quality_score,
            execution_time=execution_time,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            success=success,
            error=error
        )

        self.performance_history.append(performance)

        # Update version statistics
        version = self.get_version(version_id)
        if version:
            version.usage_count += 1

            # Update running averages
            n = version.usage_count
            version.avg_quality_score = (version.avg_quality_score * (n - 1) + quality_score) / n
            version.avg_execution_time = (version.avg_execution_time * (n - 1) + execution_time) / n

            self._save_version(version)

    def get_version_history(self, prompt_name: str) -> List[PromptVersion]:
        """Get version history sorted by creation time"""
        versions = self.get_all_versions(prompt_name)
        return sorted(versions, key=lambda v: v.created_at)

    def compare_versions(
        self,
        version_id_1: str,
        version_id_2: str
    ) -> Dict[str, Any]:
        """
        Compare two versions

        Returns:
            Comparison data with performance differences
        """
        v1 = self.get_version(version_id_1)
        v2 = self.get_version(version_id_2)

        if not v1 or not v2:
            return {}

        return {
            "version_1": {
                "id": v1.version_id,
                "quality": v1.avg_quality_score,
                "execution_time": v1.avg_execution_time,
                "usage_count": v1.usage_count
            },
            "version_2": {
                "id": v2.version_id,
                "quality": v2.avg_quality_score,
                "execution_time": v2.avg_execution_time,
                "usage_count": v2.usage_count
            },
            "differences": {
                "quality_improvement": v2.avg_quality_score - v1.avg_quality_score,
                "time_delta": v2.avg_execution_time - v1.avg_execution_time,
                "quality_pct_change": ((v2.avg_quality_score - v1.avg_quality_score) / v1.avg_quality_score * 100) if v1.avg_quality_score > 0 else 0
            }
        }

    def _get_next_version_number(self, prompt_name: str) -> int:
        """Get next version number"""
        versions = self.prompts.get(prompt_name, [])
        return len(versions) + 1

    def _save_version(self, version: PromptVersion):
        """Save version to disk"""
        filepath = self.storage_dir / f"{version.version_id}.json"

        with open(filepath, "w") as f:
            json.dump(version.to_dict(), f, indent=2)


class PromptOptimizer:
    """
    Automated prompt optimization using LLM-as-judge

    Uses an LLM to evaluate and suggest improvements to prompts.

    Example:
        ```python
        optimizer = PromptOptimizer(library=library)

        # Optimize prompt
        improved_version = optimizer.optimize_prompt(
            prompt_name="trend_summarizer",
            test_cases=[
                {"data": "...", "expected": "..."},
            ]
        )
        ```
    """

    def __init__(
        self,
        library: PromptLibrary,
        judge_llm: Optional[Any] = None
    ):
        """
        Initialize optimizer

        Args:
            library: PromptLibrary instance
            judge_llm: LLM for evaluation (uses default if None)
        """
        self.library = library
        self.judge_llm = judge_llm or self._get_default_llm()

    def _get_default_llm(self):
        """Get default LLM for judging"""
        from agents.news_trend_agent.tools import _get_llm
        return _get_llm()

    def optimize_prompt(
        self,
        prompt_name: str,
        test_cases: List[Dict[str, Any]],
        num_iterations: int = 3
    ) -> PromptVersion:
        """
        Optimize prompt using LLM-as-judge

        Args:
            prompt_name: Prompt to optimize
            test_cases: Test cases with inputs and expected outputs
            num_iterations: Number of optimization iterations

        Returns:
            Optimized PromptVersion
        """
        current_version = self.library.get_latest_version(prompt_name)
        if not current_version:
            raise ValueError(f"Prompt '{prompt_name}' not found")

        logger.info(f"Optimizing prompt '{prompt_name}' over {num_iterations} iterations")

        for iteration in range(num_iterations):
            # Evaluate current version
            score = self._evaluate_prompt(current_version, test_cases)

            logger.info(f"Iteration {iteration + 1}: score={score:.3f}")

            # Generate improved version
            improved_template = self._generate_improvement(
                current_version,
                test_cases,
                score
            )

            # Create new version
            new_version = self.library.create_version(
                prompt_name=prompt_name,
                template=improved_template,
                variables=current_version.variables,
                parent_version_id=current_version.version_id,
                description=f"LLM-optimized iteration {iteration + 1}",
                optimization_strategy=OptimizationStrategy.LLM_JUDGE
            )

            current_version = new_version

        return current_version

    def _evaluate_prompt(
        self,
        version: PromptVersion,
        test_cases: List[Dict[str, Any]]
    ) -> float:
        """Evaluate prompt quality on test cases"""
        scores = []

        for test_case in test_cases:
            # This is a simplified evaluation
            # In production, would actually execute prompt and compare
            scores.append(0.7)  # Placeholder

        return sum(scores) / len(scores) if scores else 0.0

    def _generate_improvement(
        self,
        version: PromptVersion,
        test_cases: List[Dict[str, Any]],
        current_score: float
    ) -> str:
        """Generate improved prompt template using LLM"""
        improvement_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a prompt engineering expert. Improve the given prompt."),
            ("user", """
Current prompt:
{current_template}

Current score: {score:.3f}

Test cases:
{test_cases}

Suggest an improved version of this prompt that will score higher.
Return ONLY the improved prompt template, nothing else.
            """)
        ])

        chain = improvement_prompt | self.judge_llm | StrOutputParser()

        improved = chain.invoke({
            "current_template": version.template,
            "score": current_score,
            "test_cases": json.dumps(test_cases[:3], indent=2)  # Show first 3
        })

        return improved.strip()


# Example usage
if __name__ == "__main__":
    # Initialize library
    library = PromptLibrary()

    # Register initial prompt
    v1 = library.register_prompt(
        prompt_name="trend_summarizer",
        template="""당신은 소비자 트렌드 분석 전문가입니다.

다음 데이터를 분석하고 핵심 인사이트를 제공해주세요:
{data}

분석 결과를 명확하고 실행 가능한 권고사항과 함께 제시해주세요.""",
        variables=["data"],
        description="Summarizes consumer trend data",
        tags=["trend", "analysis"],
        created_by="initial_setup"
    )

    print(f"Registered: {v1.version_id}")

    # Create improved version
    v2 = library.create_version(
        prompt_name="trend_summarizer",
        template="""당신은 소비자 트렌드 분석 전문가입니다.

다음 데이터를 깊이 분석하고 핵심 인사이트를 제공해주세요:
{data}

특별히 다음 관점에 집중해주세요:
- 감성 트렌드 (긍정/부정/중립)
- 주요 키워드와 토픽
- 시장 기회와 위험

분석 결과를 명확하고 실행 가능한 권고사항과 함께 제시해주세요.""",
        variables=["data"],
        description="Improved version with structured analysis",
        optimization_strategy=OptimizationStrategy.MANUAL
    )

    print(f"Created v2: {v2.version_id}")

    # Record performance
    library.record_performance(
        version_id=v1.version_id,
        query="AI trends",
        quality_score=0.75,
        execution_time=2.5,
        tokens_used=500,
        cost_usd=0.01
    )

    library.record_performance(
        version_id=v2.version_id,
        query="AI trends",
        quality_score=0.85,
        execution_time=3.0,
        tokens_used=600,
        cost_usd=0.012
    )

    # Compare versions
    comparison = library.compare_versions(v1.version_id, v2.version_id)
    print(f"\nComparison:")
    print(f"Quality improvement: {comparison['differences']['quality_improvement']:.3f}")
    print(f"Quality % change: {comparison['differences']['quality_pct_change']:.1f}%")

    # Get best version
    best = library.get_best_version("trend_summarizer")
    print(f"\nBest version: {best.version_id} (score: {best.avg_quality_score:.3f})")
