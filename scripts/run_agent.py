#!/usr/bin/env python3
"""
Agent Runner - CLI utility to execute agents with consistent interface

Usage:
    python scripts/run_agent.py --agent news_trend_agent --query "electric vehicles" --window 7d
    python scripts/run_agent.py --agent viral_video_agent --market KR --platform youtube,tiktok
"""
import sys
import os
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_news_trend_agent(args):
    """Run news trend agent"""
    from agents.news_trend_agent.graph import run_agent

    print(f"\n{'='*80}")
    print(f"🔍 News Trend Agent")
    print(f"{'='*80}")
    print(f"Query: {args.query}")
    print(f"Time Window: {args.window}")
    print(f"Language: {args.language}")
    print(f"Max Results: {args.max_results}")
    print(f"{'='*80}\n")

    try:
        final_state = run_agent(
            query=args.query,
            time_window=args.window,
            language=args.language,
            max_results=args.max_results
        )

        return final_state
    except Exception as e:
        print(f"❌ Error running agent: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_viral_video_agent(args):
    """Run viral video agent"""
    from agents.viral_video_agent.graph import run_agent

    platforms = args.platform.split(',') if args.platform else ['youtube']

    print(f"\n{'='*80}")
    print(f"📹 Viral Video Agent")
    print(f"{'='*80}")
    print(f"Query: {args.query}")
    print(f"Market: {args.market}")
    print(f"Platforms: {', '.join(platforms)}")
    print(f"Time Window: {args.window}")
    print(f"{'='*80}\n")

    try:
        final_state = run_agent(
            query=args.query,
            market=args.market,
            platforms=platforms,
            time_window=args.window
        )

        return final_state
    except Exception as e:
        print(f"❌ Error running agent: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def save_output(final_state, agent_name, emit_format='md', notify_channels=None):
    """Save agent output and send notifications"""

    # Create artifacts directory
    artifacts_dir = project_root / 'artifacts' / agent_name
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_id = final_state.get('run_id') or timestamp

    # Save markdown report
    if emit_format == 'md' or 'md' in emit_format.split(','):
        md_file = artifacts_dir / f"{run_id}.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(final_state.get('report_md', ''))
        print(f"\n✅ Markdown report saved: {md_file}")

    # Save JSON output
    if emit_format == 'json' or 'json' in emit_format.split(','):
        json_file = artifacts_dir / f"{run_id}.json"
        output_data = {
            'run_id': final_state.get('run_id'),
            'query': final_state.get('query'),
            'time_window': final_state.get('time_window'),
            'analysis': final_state.get('analysis', {}),
            'metrics': final_state.get('metrics', {}),
            'total_items': len(final_state.get('normalized', [])),
            'report_md': final_state.get('report_md', '')
        }
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON output saved: {json_file}")

    # Save metadata/metrics
    metrics_file = artifacts_dir / f"{run_id}_metrics.json"
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump({
            'run_id': final_state.get('run_id'),
            'timestamp': timestamp,
            'metrics': final_state.get('metrics', {}),
            'item_count': len(final_state.get('normalized', []))
        }, f, indent=2)
    print(f"✅ Metrics saved: {metrics_file}")

    # Send notifications
    if notify_channels:
        channels = notify_channels.split(',')
        for channel in channels:
            channel = channel.strip()
            if channel == 'n8n':
                send_n8n_notification(final_state)
            elif channel == 'slack':
                send_slack_notification(final_state)
            else:
                print(f"⚠️  Unknown notification channel: {channel}")

    return md_file


def send_n8n_notification(final_state):
    """Send notification to n8n webhook"""
    n8n_url = os.getenv('N8N_WEBHOOK_URL')

    if not n8n_url:
        print("⚠️  N8N_WEBHOOK_URL not configured, skipping n8n notification")
        return

    import requests

    payload = {
        'run_id': final_state.get('run_id'),
        'query': final_state.get('query'),
        'metrics': final_state.get('metrics', {}),
        'summary': final_state.get('analysis', {}).get('summary', 'No summary'),
        'timestamp': datetime.now().isoformat()
    }

    try:
        response = requests.post(n8n_url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"✅ n8n notification sent successfully")
    except Exception as e:
        print(f"❌ Failed to send n8n notification: {e}")


def send_slack_notification(final_state):
    """Send notification to Slack webhook"""
    slack_url = os.getenv('SLACK_WEBHOOK_URL')

    if not slack_url:
        print("⚠️  SLACK_WEBHOOK_URL not configured, skipping Slack notification")
        return

    import requests

    # Build Slack message
    sentiment = final_state.get('analysis', {}).get('sentiment', {})
    keywords = final_state.get('analysis', {}).get('keywords', {}).get('top_keywords', [])[:5]

    message = {
        'text': f"🔍 Agent Run Complete: {final_state.get('query')}",
        'blocks': [
            {
                'type': 'header',
                'text': {
                    'type': 'plain_text',
                    'text': f"📊 Analysis: {final_state.get('query')}"
                }
            },
            {
                'type': 'section',
                'fields': [
                    {
                        'type': 'mrkdwn',
                        'text': f"*Run ID:*\n`{final_state.get('run_id')}`"
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Items Analyzed:*\n{len(final_state.get('normalized', []))}"
                    }
                ]
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f"*Sentiment:* 😊 {sentiment.get('positive', 0)} | 😐 {sentiment.get('neutral', 0)} | 😞 {sentiment.get('negative', 0)}"
                }
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f"*Top Keywords:* {', '.join([kw['keyword'] for kw in keywords])}"
                }
            }
        ]
    }

    try:
        response = requests.post(slack_url, json=message, timeout=10)
        response.raise_for_status()
        print(f"✅ Slack notification sent successfully")
    except Exception as e:
        print(f"❌ Failed to send Slack notification: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Run consumer trend analysis agents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # News trend agent (Korean)
  python scripts/run_agent.py --agent news_trend_agent --query "전기차" --window 7d --language ko

  # News trend agent (English)
  python scripts/run_agent.py --agent news_trend_agent --query "electric vehicles" --window 24h --language en

  # Viral video agent
  python scripts/run_agent.py --agent viral_video_agent --query "trending topics" --market KR --platform youtube,tiktok

  # With notifications
  python scripts/run_agent.py --agent news_trend_agent --query "AI trends" --notify n8n,slack --emit md,json
        """
    )

    # Required arguments
    parser.add_argument('--agent', required=True,
                       choices=['news_trend_agent', 'viral_video_agent'],
                       help='Agent to run')
    parser.add_argument('--query', required=True,
                       help='Search query or topic')

    # Common optional arguments
    parser.add_argument('--window', default='7d',
                       help='Time window (e.g., 24h, 7d, 30d) [default: 7d]')
    parser.add_argument('--emit', default='md',
                       help='Output format: md, json, or md,json [default: md]')
    parser.add_argument('--notify', default=None,
                       help='Notification channels: n8n, slack, or n8n,slack')

    # News trend agent specific
    parser.add_argument('--language', default='ko',
                       help='Language for news search (ko, en) [default: ko]')
    parser.add_argument('--max-results', type=int, default=20,
                       help='Maximum number of results [default: 20]')

    # Viral video agent specific
    parser.add_argument('--market', default='KR',
                       help='Market code (KR, US, JP, etc) [default: KR]')
    parser.add_argument('--platform', default='youtube',
                       help='Platforms: youtube, tiktok, or youtube,tiktok [default: youtube]')

    args = parser.parse_args()

    # Run appropriate agent
    if args.agent == 'news_trend_agent':
        final_state = run_news_trend_agent(args)
    elif args.agent == 'viral_video_agent':
        final_state = run_viral_video_agent(args)
    else:
        print(f"❌ Unknown agent: {args.agent}")
        sys.exit(1)

    # Display report
    print(f"\n{'='*80}")
    print("📄 REPORT")
    print(f"{'='*80}\n")
    print(final_state.get("report_md", "No report generated"))
    print(f"\n{'='*80}")

    # Display metrics
    print("\n📊 METRICS")
    print(f"{'='*80}")
    print(json.dumps(final_state.get("metrics", {}), indent=2))
    print(f"{'='*80}\n")

    # Save output and notify
    output_file = save_output(final_state, args.agent, args.emit, args.notify)

    print(f"\n✨ Agent execution completed successfully!")
    print(f"📁 Output: {output_file}")
    print(f"🆔 Run ID: {final_state.get('run_id')}\n")


if __name__ == '__main__':
    main()
