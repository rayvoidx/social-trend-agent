"""
버전 4.0 엔터프라이즈 기능 - 완전한 예제

모든 v4.0 기능을 통합하여 시연합니다:
- 분산 실행
- 실시간 대시보드 API
- A/B 테스팅
- 프롬프트 버전 관리
- 설정 관리
- 레이트 리미팅

이 예제는 최적화 및 모니터링과 함께 대규모로
소비자 트렌드 분석을 실행하기 위한 프로덕션 수준의 워크플로우를 보여줍니다.
"""
import asyncio
import time
from typing import Dict, Any
import logging

# v4.0 imports
from agents.shared.distributed import DistributedAgentExecutor, TaskPriority
from agents.shared.ab_testing import ABExperiment, AgentVariant, VariantType
from agents.shared.prompt_versioning import PromptLibrary, PromptOptimizer
from agents.shared.config_manager import initialize_config, get_config_manager
from agents.shared.rate_limiter import get_rate_limiter
from agents.shared.monitoring import PerformanceMonitor
from agents.shared.evaluation import AgentEvaluator

# Agent imports
from agents.news_trend_agent.graph import run_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# 1단계: 설정 초기화
# ============================================================================

def setup_configuration():
    """설정 관리 초기화"""
    logger.info("=== 설정 구성 중 ===")

    # 파일에서 설정 초기화
    initialize_config(config_dir="config")

    config = get_config_manager()

    # 현재 설정 로깅
    logger.info(f"Environment: {config.environment.value}")
    logger.info(f"LLM Provider: {config.get_llm_config().provider}")
    logger.info(f"Distributed enabled: {config.config.distributed_enabled}")

    return config


# ============================================================================
# 2단계: 레이트 리미팅 설정
# ============================================================================

def setup_rate_limiting(config):
    """모든 제공자에 대한 레이트 리미터 설정"""
    logger.info("=== 레이트 리미팅 설정 중 ===")

    limiter = get_rate_limiter()

    # 설정에 기반하여 제공자 등록
    limiter.register_provider(
        "openai",
        requests_per_minute=60,
        requests_per_hour=3000,
        requests_per_day=100000,
        tokens_per_minute=90000,
        cost_per_day_usd=50.0,
        burst_size=10
    )

    limiter.register_provider(
        "newsapi",
        requests_per_minute=100,
        requests_per_hour=5000,
        requests_per_day=100000
    )

    logger.info("Rate limiting configured for all providers")

    return limiter


# ============================================================================
# 3단계: 프롬프트 라이브러리 설정
# ============================================================================

def setup_prompt_library():
    """버전이 있는 프롬프트 라이브러리 초기화"""
    logger.info("=== 프롬프트 라이브러리 설정 중 ===")

    library = PromptLibrary(storage_dir="artifacts/prompts")

    # 기본 프롬프트 등록
    v1 = library.register_prompt(
        prompt_name="trend_summarizer",
        template="""당신은 소비자 트렌드 분석 전문가입니다.

다음 데이터를 분석하고 핵심 인사이트를 제공해주세요:
{data}

분석 결과를 명확하고 실행 가능한 권고사항과 함께 제시해주세요.""",
        variables=["data"],
        description="Base trend summarizer",
        tags=["trend", "analysis"],
        created_by="system"
    )

    logger.info(f"Registered prompt: {v1.version_id}")

    # 최적화된 버전 생성
    v2 = library.create_version(
        prompt_name="trend_summarizer",
        template="""당신은 소비자 트렌드 분석 전문가입니다.

다음 데이터를 깊이 분석하고 핵심 인사이트를 제공해주세요:
{data}

특별히 다음 관점에 집중해주세요:
- 감성 트렌드 (긍정/부정/중립)
- 주요 키워드와 토픽
- 시장 기회와 위험
- 실행 가능한 권고사항

분석 결과를 구조화된 형식으로 제시해주세요.""",
        variables=["data"],
        description="Enhanced with structured analysis",
        parent_version_id=v1.version_id
    )

    logger.info(f"Created enhanced version: {v2.version_id}")

    return library


# ============================================================================
# 4단계: A/B 실험 생성
# ============================================================================

def create_ab_experiment():
    """프롬프트 변형을 위한 A/B 테스트 생성"""
    logger.info("=== A/B 실험 생성 중 ===")

    experiment = ABExperiment(
        name="prompt_optimization_v1",
        variants={
            "control": AgentVariant(
                name="control",
                variant_type=VariantType.CONTROL,
                config={"prompt_version": "trend_summarizer_v1"},
                traffic_allocation=0.5,
                description="Original prompt"
            ),
            "treatment": AgentVariant(
                name="treatment",
                variant_type=VariantType.TREATMENT,
                config={"prompt_version": "trend_summarizer_v2"},
                traffic_allocation=0.5,
                description="Enhanced prompt with structure"
            )
        },
        description="Testing enhanced prompt structure",
        min_sample_size=10,
        confidence_threshold=0.95
    )

    experiment.start()

    logger.info(f"Experiment started: {experiment.name}")
    logger.info(f"Variants: {list(experiment.variants.keys())}")

    return experiment


# ============================================================================
# 5단계: 분산 실행 설정
# ============================================================================

async def setup_distributed_executor():
    """분산 에이전트 실행기 초기화"""
    logger.info("=== 분산 실행기 설정 중 ===")

    executor = DistributedAgentExecutor(
        num_workers=4,
        agent_executor=run_agent
    )

    # 워커 시작
    await executor.start()

    logger.info(f"Started {executor.num_workers} workers")

    return executor


# ============================================================================
# 6단계: 프로덕션 워크플로우 실행
# ============================================================================

async def run_production_workflow(
    executor: DistributedAgentExecutor,
    experiment: ABExperiment,
    library: PromptLibrary,
    limiter
):
    """모든 v4.0 기능을 갖춘 프로덕션 워크플로우 실행"""
    logger.info("=== 프로덕션 워크플로우 실행 중 ===")

    # 테스트 쿼리
    test_queries = [
        "AI trends 2025",
        "전기차 시장",
        "sustainable fashion",
        "메타버스 플랫폼",
        "cloud computing",
        "renewable energy",
        "cryptocurrency regulation",
        "remote work technology"
    ]

    task_ids = []

    # A/B 테스팅과 함께 태스크 제출
    for i, query in enumerate(test_queries):
        # 변형 할당
        variant = experiment.assign_variant()

        logger.info(f"Query {i+1}: '{query}' → {variant.name}")

        # 레이트 제한 확인
        result = limiter.check_rate_limit("openai", tokens=1000)

        if not result.allowed:
            logger.warning(f"Rate limited: {result.reason}, waiting {result.wait_time_seconds:.2f}s")
            await asyncio.sleep(result.wait_time_seconds)

        # 태스크 제출
        task_id = await executor.submit_task(
            agent_name="news_trend_agent",
            query=query,
            params={
                "time_window": "7d",
                "max_results": 10,
                "variant": variant.name
            },
            priority=TaskPriority.NORMAL
        )

        task_ids.append((task_id, query, variant))

        # 레이트 제한 사용량 기록
        limiter.record_request("openai", tokens_used=1000, cost_usd=0.02)

        # 제출 사이의 짧은 지연
        await asyncio.sleep(0.5)

    logger.info(f"Submitted {len(task_ids)} tasks")

    # 결과 대기 및 평가
    evaluator = AgentEvaluator()

    for task_id, query, variant in task_ids:
        try:
            # 타임아웃과 함께 결과 대기
            result = await executor.wait_for_result(task_id, timeout=120)

            logger.info(f"Task {task_id[:8]} completed")

            # 결과 평가
            if result and isinstance(result, dict):
                eval_metrics = evaluator.evaluate(query, result)

                logger.info(
                    f"Evaluation: score={eval_metrics.overall_score:.2f}, "
                    f"level={eval_metrics.level.value}"
                )

                # 실험 결과 기록
                experiment.record_result(
                    variant_name=variant.name,
                    query=query,
                    execution_time=result.get('metrics', {}).get('duration', 0),
                    quality_score=eval_metrics.overall_score,
                    metrics={
                        "relevance": eval_metrics.relevance,
                        "completeness": eval_metrics.completeness,
                        "accuracy": eval_metrics.accuracy,
                        "actionability": eval_metrics.actionability
                    }
                )

                # 프롬프트 성능 기록
                prompt_version = variant.config.get("prompt_version", "unknown")
                library.record_performance(
                    version_id=prompt_version,
                    query=query,
                    quality_score=eval_metrics.overall_score,
                    execution_time=result.get('metrics', {}).get('duration', 0),
                    tokens_used=1000,
                    cost_usd=0.02
                )

        except asyncio.TimeoutError:
            logger.error(f"Task {task_id[:8]} timed out")
        except Exception as e:
            logger.error(f"Task {task_id[:8]} failed: {e}")

    return task_ids


# ============================================================================
# 7단계: 결과 분석
# ============================================================================

def analyze_results(experiment: ABExperiment, library: PromptLibrary, limiter):
    """실험 및 시스템 성능 분석"""
    logger.info("=== 결과 분석 중 ===")

    # A/B 실험 분석
    logger.info("\n--- A/B 테스트 결과 ---")
    analysis = experiment.analyze()

    logger.info(f"총 샘플 수: {analysis.total_samples}")
    logger.info(f"승자: {analysis.winner or '아직 유의미한 승자 없음'}")
    logger.info(f"P-value: {analysis.p_value:.4f}")
    logger.info(f"통계적 유의성: {analysis.is_significant}")

    for variant_name, stats in analysis.variant_stats.items():
        logger.info(f"\n{variant_name}:")
        logger.info(f"  샘플 수: {stats.sample_size}")
        logger.info(f"  평균 품질: {stats.mean_quality:.3f} ± {stats.std_quality:.3f}")
        logger.info(f"  95% CI: ({stats.confidence_interval_95[0]:.3f}, {stats.confidence_interval_95[1]:.3f})")
        logger.info(f"  평균 시간: {stats.mean_execution_time:.2f}초")

    logger.info("\n권고사항:")
    for rec in analysis.recommendations:
        logger.info(f"  - {rec}")

    # 실험 저장
    experiment_path = "artifacts/experiments/prompt_optimization_v1.json"
    experiment.save(experiment_path)
    logger.info(f"\n실험 저장 위치: {experiment_path}")

    # 프롬프트 성능
    logger.info("\n--- 프롬프트 성능 ---")
    best_prompt = library.get_best_version("trend_summarizer")
    if best_prompt:
        logger.info(f"최고 프롬프트 버전: {best_prompt.version_id}")
        logger.info(f"  품질 점수: {best_prompt.avg_quality_score:.3f}")
        logger.info(f"  사용 횟수: {best_prompt.usage_count}")
        logger.info(f"  평균 실행 시간: {best_prompt.avg_execution_time:.2f}초")

    # 레이트 리미팅 상태
    logger.info("\n--- 레이트 리미팅 상태 ---")
    for provider in ["openai", "newsapi"]:
        status = limiter.get_quota_status(provider)
        if status:
            req_status = status['requests']['minute']
            logger.info(f"{provider}:")
            logger.info(f"  요청: {req_status['used']}/{req_status['limit']} (남음: {req_status['remaining']})")

            if 'cost' in status:
                cost_status = status['cost']['day']
                logger.info(f"  비용: ${cost_status['used_usd']:.2f}/${cost_status['limit_usd']:.2f}")


# ============================================================================
# 메인 실행
# ============================================================================

async def main():
    """메인 실행 흐름"""
    logger.info("========================================")
    logger.info("  버전 4.0 엔터프라이즈 기능 데모")
    logger.info("========================================\n")

    try:
        # 1단계: 설정
        config = setup_configuration()

        # 2단계: 레이트 리미팅
        limiter = setup_rate_limiting(config)

        # 3단계: 프롬프트 라이브러리
        library = setup_prompt_library()

        # 4단계: A/B 실험
        experiment = create_ab_experiment()

        # 5단계: 분산 실행기
        executor = await setup_distributed_executor()

        # 6단계: 워크플로우 실행
        await run_production_workflow(executor, experiment, library, limiter)

        # 7단계: 결과 분석
        analyze_results(experiment, library, limiter)

        # 최종 통계 조회
        logger.info("\n--- 시스템 통계 ---")
        stats = await executor.get_statistics()
        logger.info(f"총 태스크: {stats['tasks_submitted']}")
        logger.info(f"완료: {stats['tasks_completed']}")
        logger.info(f"실패: {stats['tasks_failed']}")
        logger.info(f"활성 워커: {stats['active_workers']}")

        # 실행기 중지
        logger.info("\n=== 종료 중 ===")
        await executor.stop()

        logger.info("\n✅ 데모가 성공적으로 완료되었습니다!")

    except KeyboardInterrupt:
        logger.info("\n⚠️  사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"\n❌ 에러: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
