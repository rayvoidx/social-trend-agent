"""
CLI/HTTP entrypoint for News Trend Agent
"""
import sys
import json
from agents.news_trend_agent.graph import run_agent


def main():
    """CLI entrypoint"""
    if len(sys.argv) < 2:
        print("Usage: python -m agents.news_trend_agent '<query>' [time_window] [language] [max_results]")
        print("Example: python -m agents.news_trend_agent 'electric vehicles' 7d en 20")
        sys.exit(1)

    query = sys.argv[1]
    time_window = sys.argv[2] if len(sys.argv) > 2 else "7d"
    language = sys.argv[3] if len(sys.argv) > 3 else "ko"
    max_results = int(sys.argv[4]) if len(sys.argv) > 4 else 20

    print(f"Running News Trend Agent...")
    print(f"  Query: {query}")
    print(f"  Time Window: {time_window}")
    print(f"  Language: {language}")
    print(f"  Max Results: {max_results}")
    print()

    final_state = run_agent(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results
    )

    # Print report
    print("\n" + "="*80)
    print(final_state.report_md)
    print("="*80)

    # Print metrics
    print("\nMetrics:")
    print(json.dumps(final_state.metrics, indent=2))

    # Save to file
    output_file = f"artifacts/news_trend_agent/{final_state.run_id}.md"
    import os
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_state.report_md)
    print(f"\nReport saved to: {output_file}")


if __name__ == "__main__":
    main()
