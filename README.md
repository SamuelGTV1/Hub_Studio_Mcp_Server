# StudyHub MCP Server

[![MCP Enabled](https://img.shields.io/badge/Model_Context_Protocol-Enabled-blue.svg)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org)

An open-source Model Context Protocol (MCP) server that connects your local Study Hub backup JSON to Claude Desktop, turning Claude into a context-aware, personalized study tutor.

## What this is
Study Hub is local-first, so desktop AI apps cannot read its data directly. This server bridges the gap by loading your exported JSON backup and exposing MCP tools and prompts that Claude can call.

## Why it matters
- Uses your real tasks, flashcards, streaks, and schedule to produce practical guidance.
- Keeps data local to your machine. Nothing is uploaded by this server.
- Adds one-click MCP prompts that trigger multi-tool reasoning flows.

## Features
- Context-aware tools for profile, tasks, flashcards, pomodoros, schedule, and missions.
- Built-in MCP prompts like `plan_my_day` and `review_my_flashcards`.
- Clear error messages when the backup file is missing or invalid.

## Quickstart
1. Export your data from Study Hub (Settings > Export Data) to get `CampusFlow_Backup.json`.
2. Clone this repository and set up a virtual environment:

```bash
git clone https://github.com/YOUR_USERNAME/studyhub-mcp-server.git
cd studyhub-mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Point the server to your backup file:

```bash
export STUDYHUB_BACKUP_PATH="/absolute/path/to/CampusFlow_Backup.json"
```

4. Run the server:

```bash
python3 server.py
```

## Claude Desktop setup
Add the MCP server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "studyhub": {
      "command": "/absolute/path/to/studyhub-mcp-server/.venv/bin/python",
      "args": [
        "/absolute/path/to/studyhub-mcp-server/server.py"
      ],
      "env": {
        "STUDYHUB_BACKUP_PATH": "/absolute/path/to/CampusFlow_Backup.json"
      }
    }
  }
}
```

## MCP Prompts
These prompts appear as buttons in Claude Desktop and orchestrate tool usage automatically.
- `plan_my_day`: Generates a realistic daily plan based on your tasks and schedule.
- `review_my_flashcards`: Surfaces weak decks and recommends a study focus with mission incentives.

## Tools exposed
- `get_full_summary`: Snapshot of level, XP, streak, pending tasks, due cards, and schedule.
- `get_study_profile`: Level, XP, coins, streak, garden, and XP source breakdown.
- `get_pending_tasks`: Tasks and todos sorted by priority with estimates and due dates.
- `get_flashcard_analysis`: Deck stats, due count, and hardest cards.
- `get_pomodoro_stats`: Focus sessions today and overall, plus timer config.
- `get_today_schedule`: Events and weekly schedule blocks for today.
- `get_daily_missions`: Mission progress, boss status, and chest readiness.

## Notes
- The server reads the JSON file on each tool call. Re-export the file after changes.
- If the file is missing or invalid, the tool returns a clear error message.
