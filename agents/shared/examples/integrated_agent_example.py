"""
Integration example: Using retry, cache, logging, and error handling together

This demonstrates how to build a production-ready agent node using all shared utilities.
"""
import time
from typing import Dict, Any, List
from agents.shared.retry import backoff_retry, RETRY_CONFIG_DEFAULT
from agents.shared.cache import cached
from agents.shared.logging import AgentLogger, setup_logging
from agents.shared.error_handling import (
    PartialResult,
    CompletionStatus,
    safe_api_call
)


# Setup logging at module level
setup_logging(json_format=True)


class NewsCollectorNode:
    """
    Example agent node with full production features:
    - Exponential backoff retry
    - TTL caching
    - Structured logging
    - Graceful error handling
    """

    def __init__(self, run_id: str):
        """
        Args:
            run_id: Unique identifier for this execution
        """
        self.run_id = run_id
        self.logger = AgentLogger("news_collector", run_id)

    @backoff_retry(max_retries=3, backoff_factor=0.5)
    def _fetch_from_news_api(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Fetch news from NewsAPI with retry logic

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of news articles
        """
        self.logger.info(f"Fetching from NewsAPI", query=query, max_results=max_results)

        # Simulate API call (replace with actual API)
        import random
        if random.random() < 0.3:  # 30% chance of failure
            self.logger.warning("NewsAPI call failed, will retry")
            raise ConnectionError("NewsAPI temporarily unavailable")

        # Simulate successful response
        results = [
            {
                "source": "NewsAPI",
                "title": f"Article {i} about {query}",
                "url": f"https://example.com/article-{i}",
                "publishedAt": "2024-10-19T10:00:00Z"
            }
            for i in range(max_results)
        ]

        self.logger.info(f"Fetched {len(results)} articles from NewsAPI")
        return results

    @cached(ttl=3600, use_disk=False)  # Cache for 1 hour
    def _fetch_from_naver_api(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Fetch news from Naver API with caching

        Results are cached for 1 hour to reduce API calls

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of news articles
        """
        self.logger.info(f"Fetching from Naver API (not cached)", query=query)

        # Simulate API call
        time.sleep(0.1)  # Simulate network delay

        results = [
            {
                "source": "Naver",
                "title": f"네이버 기사 {i} - {query}",
                "url": f"https://news.naver.com/article-{i}",
                "publishedAt": "2024-10-19T10:00:00Z"
            }
            for i in range(max_results)
        ]

        self.logger.info(f"Fetched {len(results)} articles from Naver")
        return results

    def collect(self, query: str, max_results: int = 20) -> PartialResult:
        """
        Collect news from multiple sources with error handling

        This method demonstrates:
        1. Using AgentLogger for structured logging
        2. Tracking operation success/failure
        3. Graceful degradation when APIs fail
        4. Returning PartialResult with metadata

        Args:
            query: Search query
            max_results: Maximum results per source

        Returns:
            PartialResult containing collected news and metadata
        """
        start_time = time.time()
        self.logger.node_start("collect", input_size=len(query))

        # Initialize partial result
        result = PartialResult(
            status=CompletionStatus.PARTIAL,
            data={"items": [], "sources": []}
        )

        # Collect from NewsAPI
        news_api_items = safe_api_call(
            "NewsAPI",
            self._fetch_from_news_api,
            query,
            max_results=max_results // 2,
            fallback_value=[],
            result_container=result
        )

        if news_api_items:
            result.data["items"].extend(news_api_items)
            result.data["sources"].append("NewsAPI")
        else:
            result.add_limitation("NewsAPI 데이터 수집 실패로 결과가 제한적일 수 있습니다")

        # Collect from Naver API
        naver_items = safe_api_call(
            "NaverAPI",
            self._fetch_from_naver_api,
            query,
            max_results=max_results // 2,
            fallback_value=[],
            result_container=result
        )

        if naver_items:
            result.data["items"].extend(naver_items)
            result.data["sources"].append("Naver")
        else:
            result.add_limitation("Naver API 데이터 수집 실패로 결과가 제한적일 수 있습니다")

        # Determine final status
        if len(result.successful_operations) == 2:
            result.status = CompletionStatus.FULL
            self.logger.info("All data sources collected successfully")
        elif len(result.successful_operations) >= 1:
            result.status = CompletionStatus.PARTIAL
            result.add_warning("일부 데이터 소스만 성공적으로 수집되었습니다")
            self.logger.warning(
                "Partial data collection",
                successful=result.successful_operations,
                failed=result.failed_operations
            )
        else:
            result.status = CompletionStatus.FAILED
            self.logger.error("All data sources failed")

        # Add metadata
        result.data["total_items"] = len(result.data["items"])
        result.data["query"] = query

        # Log completion
        duration_ms = int((time.time() - start_time) * 1000)
        self.logger.node_end(
            "collect",
            output_size=result.data["total_items"],
            duration_ms=duration_ms
        )

        return result


def example_usage():
    """Example usage of the integrated node"""
    import logging
    from agents.shared.logging import setup_logging

    # Setup logging
    setup_logging(level=logging.INFO, json_format=True)

    # Create node
    collector = NewsCollectorNode(run_id="example-run-001")

    # Collect news
    result = collector.collect(query="AI trends", max_results=10)

    # Print results
    print("\n" + "="*60)
    print("COLLECTION RESULTS")
    print("="*60)
    print(f"Status: {result.status.value}")
    print(f"Total items: {result.data.get('total_items', 0)}")
    print(f"Sources: {', '.join(result.data.get('sources', []))}")
    print(f"\nSuccessful operations: {', '.join(result.successful_operations)}")
    print(f"Failed operations: {', '.join(result.failed_operations)}")

    if result.warnings:
        print(f"\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.limitations:
        print(f"\nLimitations:")
        for limitation in result.limitations:
            print(f"  - {limitation}")

    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error['operation']}: {error['error_type']}")

    # Get markdown notice for reports
    if result.status != CompletionStatus.FULL:
        print("\n" + "="*60)
        print("MARKDOWN NOTICE FOR REPORTS")
        print("="*60)
        print(result.get_markdown_notice())

    # Serialize to JSON
    print("\n" + "="*60)
    print("JSON SERIALIZATION")
    print("="*60)
    import json
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    return result


def example_with_multiple_nodes():
    """
    Example of chaining multiple nodes with error handling
    """
    from agents.shared.logging import setup_logging
    import logging

    setup_logging(level=logging.INFO, json_format=True)

    run_id = "multi-node-example"
    logger = AgentLogger("multi_node_workflow", run_id)

    logger.info("Starting multi-node workflow")

    # Node 1: Collect
    collector = NewsCollectorNode(run_id=run_id)
    collect_result = collector.collect(query="electric vehicles", max_results=20)

    if not collect_result.is_usable():
        logger.error("Collection failed, cannot proceed")
        return None

    # Node 2: Analyze (simplified example)
    logger.node_start("analyze", input_size=collect_result.data["total_items"])

    analyze_result = PartialResult(
        status=CompletionStatus.FULL,
        data={
            "sentiment": {"positive": 15, "neutral": 3, "negative": 2},
            "keywords": ["electric", "vehicle", "battery", "charging"]
        }
    )

    logger.node_end("analyze", output_size=4, duration_ms=150)

    # Node 3: Summarize
    logger.node_start("summarize")

    summary_result = PartialResult(
        status=CompletionStatus.FULL,
        data={
            "summary": "Electric vehicle trends show strong positive sentiment...",
            "top_keywords": analyze_result.data["keywords"][:3]
        }
    )

    logger.node_end("summarize", output_size=1, duration_ms=200)

    # Combine results
    final_result = PartialResult(
        status=CompletionStatus.FULL,
        data={
            "collection": collect_result.data,
            "analysis": analyze_result.data,
            "summary": summary_result.data
        }
    )

    # Propagate any warnings/limitations from collection
    final_result.warnings.extend(collect_result.warnings)
    final_result.limitations.extend(collect_result.limitations)

    if collect_result.status == CompletionStatus.PARTIAL:
        final_result.status = CompletionStatus.PARTIAL

    logger.info("Multi-node workflow completed", status=final_result.status.value)

    return final_result


if __name__ == "__main__":
    print("\n" + "="*70)
    print("EXAMPLE 1: Single Node with Error Handling")
    print("="*70)
    example_usage()

    print("\n\n" + "="*70)
    print("EXAMPLE 2: Multi-Node Workflow")
    print("="*70)
    result = example_with_multiple_nodes()

    if result:
        print(f"\nFinal workflow status: {result.status.value}")
        print(f"Warnings: {len(result.warnings)}")
        print(f"Limitations: {len(result.limitations)}")
