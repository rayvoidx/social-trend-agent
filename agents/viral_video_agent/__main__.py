"""
CLI/HTTP entrypoint for Viral Video Agent
"""
import sys
import json
from agents.viral_video_agent.graph import run_agent


def main():
    """CLI entrypoint"""
    if len(sys.argv) < 2:
        print("Usage: python -m agents.viral_video_agent '<query>' [market] [platforms] [time_window] [threshold]")
        print("Example: python -m agents.viral_video_agent 'trending' KR youtube,tiktok 24h 2.0")
        sys.exit(1)

    query = sys.argv[1]
    market = sys.argv[2] if len(sys.argv) > 2 else "KR"
    platforms = sys.argv[3].split(",") if len(sys.argv) > 3 else ["youtube"]
    time_window = sys.argv[4] if len(sys.argv) > 4 else "24h"
    spike_threshold = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0

    print(f"Running Viral Video Agent...")
    print(f"  Query: {query}")
    print(f"  Market: {market}")
    print(f"  Platforms: {', '.join(platforms)}")
    print(f"  Time Window: {time_window}")
    print(f"  Spike Threshold: {spike_threshold}")
    print()

    final_state = run_agent(
        query=query,
        market=market,
        platforms=platforms,
        time_window=time_window,
        spike_threshold=spike_threshold
    )

    # Print report
    print("\n" + "="*80)
    print(final_state.report_md)
    print("="*80)

    # Print metrics
    print("\nMetrics:")
    print(json.dumps(final_state.metrics, indent=2))

    # Save to file
    output_file = f"artifacts/viral_video_agent/{final_state.run_id}.md"
    import os
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_state.report_md)
    print(f"\nReport saved to: {output_file}")


if __name__ == "__main__":
    main()
