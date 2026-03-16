from __future__ import annotations

import json
import math
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP

SERVER_NAME = "StudyHub"
DEFAULT_BACKUP_FILENAME = "CampusFlow_Backup.json"
BACKUP_ENV_VAR = "STUDYHUB_BACKUP_PATH"
BACKUP_PATH = os.getenv(BACKUP_ENV_VAR, DEFAULT_BACKUP_FILENAME)

mcp = FastMCP(SERVER_NAME)

_CACHE: Dict[str, Any] = {"path": None, "mtime": None, "data": None}


def _resolve_path() -> Path:
    path = Path(BACKUP_PATH).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def load_data() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    path = _resolve_path()
    if not path.exists():
        return None, (
            "Study Hub data file not found. "
            f"Current path: {path}. "
            f"Export the JSON and/or set {BACKUP_ENV_VAR}."
        )
    if not path.is_file():
        return None, (
            "Configured path is not a valid file. "
            f"Current path: {path}."
        )

    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        return None, f"Could not read the file metadata: {exc}"

    cache_path = str(path)
    if (
        _CACHE.get("path") == cache_path
        and _CACHE.get("mtime") == mtime
        and isinstance(_CACHE.get("data"), dict)
    ):
        return _CACHE["data"], None

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        return None, (
            "The file is not valid JSON. "
            f"Error: {exc.msg} (line {exc.lineno}, column {exc.colno})."
        )
    except OSError as exc:
        return None, f"Error reading the file: {exc}"

    if not isinstance(data, dict):
        return None, "The JSON root is not an object."

    _CACHE["path"] = cache_path
    _CACHE["mtime"] = mtime
    _CACHE["data"] = data
    return data, None


def _as_list(data: Dict[str, Any], key: str) -> List[Any]:
    value = data.get(key)
    return value if isinstance(value, list) else []


def _as_dict(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _today_iso() -> str:
    return date.today().isoformat()


def _date_from_string(value: Any) -> Optional[date]:
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _datetime_from_any(value: Any) -> Optional[datetime]:
    if isinstance(value, (int, float)):
        seconds = value / 1000.0 if value > 1e12 else float(value)
        try:
            return datetime.fromtimestamp(seconds)
        except (OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
        d = _date_from_string(raw)
        if d:
            return datetime(d.year, d.month, d.day)
    return None


def _short(text: Any, max_len: int = 80) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def _priority_rank(priority: Any) -> int:
    value = str(priority or "").strip().lower()
    if value in ("alta", "high"):
        return 0
    if value in ("media", "medium"):
        return 1
    if value in ("baja", "low"):
        return 2
    return 3


def _level_from_xp(total_xp: int) -> Dict[str, int]:
    level = 1
    need = 500
    left = max(0, int(total_xp))
    while left >= need:
        left -= need
        level += 1
        need = int(math.ceil(need * 1.1))
    return {"level": level, "into": left, "need": need}


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(math.ceil(p * (len(ordered) - 1)))
    return float(ordered[max(0, min(idx, len(ordered) - 1))])


def _sum(values: Iterable[float]) -> float:
    total = 0.0
    for v in values:
        total += float(v)
    return total


@mcp.tool()
def get_study_profile() -> str:
    """Returns the user's level, XP, coins, streak, and garden status."""
    data, err = load_data()
    if err:
        return err

    xp_ledger = _as_list(data, "cf_xp")
    total_xp = sum(_safe_int(entry.get("amount", entry.get("value", 0))) for entry in xp_ledger)
    level_data = _level_from_xp(total_xp)

    coins = _as_dict(data, "cf_coins")
    focus_coins = _safe_int(coins.get("focus", coins.get("coins", 0)))

    streak = _as_dict(data, "cf_streak")
    streak_days = _safe_int(streak.get("days", 0))
    max_days = _safe_int(streak.get("maxDays", 0))
    max_srs = _safe_int(streak.get("maxSrsStreak", 0))
    jokers = _safe_int(streak.get("jokers", 0))
    last_date = streak.get("lastDate") if isinstance(streak.get("lastDate"), str) else ""

    garden = _as_dict(data, "cf_garden")
    garden_level = _safe_int(garden.get("level", 1))
    garden_growth = _safe_int(garden.get("growth", 0))
    garden_items = garden.get("items") if isinstance(garden.get("items"), list) else []

    xp_by_source: Dict[str, int] = {}
    for entry in xp_ledger:
        source = str(entry.get("source", "misc")).strip() or "misc"
        amount = _safe_int(entry.get("amount", entry.get("value", 0)))
        xp_by_source[source] = xp_by_source.get(source, 0) + amount

    source_lines = []
    if xp_by_source:
        top_sources = sorted(xp_by_source.items(), key=lambda x: x[1], reverse=True)[:5]
        source_lines = [f"- {src}: {amt} XP" for src, amt in top_sources]

    xp_boost = _as_dict(data, "cf_xp_boost")
    boost_mult = _safe_float(xp_boost.get("multiplier", 1.0), 1.0)
    boost_expires = _safe_int(xp_boost.get("expiresAt", 0))
    boost_active = boost_mult > 1 and boost_expires > 0 and boost_expires > int(datetime.now().timestamp() * 1000)

    lines = [
        "Study Hub Profile:",
        f"- Level: {level_data['level']} (XP {total_xp}; progress {level_data['into']}/{level_data['need']})",
        f"- Focus Coins: {focus_coins}",
        f"- Streak: {streak_days} days (max {max_days}, max SRS {max_srs}, jokers {jokers}, last active {last_date or 'N/A'})",
        f"- Garden: level {garden_level}, growth {garden_growth}, items {len(garden_items)}",
    ]

    if boost_active:
        minutes_left = max(0, int((boost_expires - int(datetime.now().timestamp() * 1000)) / 60000))
        lines.append(f"- XP Boost active: x{boost_mult:g} (~{minutes_left} min)")

    if source_lines:
        lines.append("XP by source (top 5):")
        lines.extend(source_lines)

    return "\n".join(lines)


@mcp.tool()
def get_pending_tasks() -> str:
    """Returns pending tasks and todos with priority and estimates."""
    data, err = load_data()
    if err:
        return err

    tasks = _as_list(data, "cf_tasks")
    todos = _as_list(data, "cf_todos")

    pending_tasks = [t for t in tasks if isinstance(t, dict) and not t.get("done")]
    pending_todos = [t for t in todos if isinstance(t, dict) and not t.get("done")]

    if not pending_tasks and not pending_todos:
        return "No pending tasks or todos."

    def task_sort_key(task: Dict[str, Any]) -> Tuple[int, str]:
        priority = _priority_rank(task.get("priority"))
        due = task.get("dueAt")
        due_key = due if isinstance(due, str) and due else "9999-12-31"
        return priority, due_key

    pending_tasks.sort(key=task_sort_key)

    lines = []
    if pending_tasks:
        lines.append(f"Pending tasks ({len(pending_tasks)}):")
        for task in pending_tasks[:12]:
            title = _short(task.get("title", "Untitled"), 90)
            priority_raw = str(task.get("priority", "medium")).lower() or "medium"
            priority = {
                "alta": "high",
                "high": "high",
                "media": "medium",
                "medium": "medium",
                "baja": "low",
                "low": "low",
            }.get(priority_raw, priority_raw)
            estimate = _safe_int(task.get("estimateMin", 25), 25)
            due = task.get("dueAt") if isinstance(task.get("dueAt"), str) else ""
            extra = f"priority: {priority}, est: {estimate}m"
            if due:
                extra += f", due: {due}"
            lines.append(f"- {title} ({extra})")
        if len(pending_tasks) > 12:
            lines.append(f"- ...and {len(pending_tasks) - 12} more tasks")

    if pending_todos:
        if lines:
            lines.append("")
        lines.append(f"Pending todos ({len(pending_todos)}):")
        for todo in pending_todos[:12]:
            text = _short(todo.get("text", "Untitled"), 90)
            lines.append(f"- {text}")
        if len(pending_todos) > 12:
            lines.append(f"- ...and {len(pending_todos) - 12} more todos")

    return "\n".join(lines)


@mcp.tool()
def get_flashcard_analysis() -> str:
    """Flashcard analysis: decks, due cards, and hardest items."""
    data, err = load_data()
    if err:
        return err

    cards = _as_list(data, "cf_cards")
    if not cards:
        return "No flashcards found."

    now = datetime.now()

    deck_stats: Dict[str, Dict[str, float]] = {}
    scores: List[float] = []
    scored_cards: List[Tuple[float, Dict[str, Any]]] = []
    due_count = 0

    for card in cards:
        if not isinstance(card, dict):
            continue
        deck = str(card.get("deck", "Personal")).strip() or "Personal"
        ease = _safe_float(card.get("ease", 2.5), 2.5)
        lapses = _safe_int(card.get("lapses", 0))
        reps = _safe_int(card.get("reps", 0))

        due_dt = _datetime_from_any(card.get("due"))
        is_due = True if due_dt is None else due_dt <= now
        if is_due:
            due_count += 1

        if deck not in deck_stats:
            deck_stats[deck] = {"count": 0, "due": 0, "ease_sum": 0.0, "lapses_sum": 0.0}
        deck_stats[deck]["count"] += 1
        deck_stats[deck]["due"] += 1 if is_due else 0
        deck_stats[deck]["ease_sum"] += ease
        deck_stats[deck]["lapses_sum"] += lapses

        score = (lapses * 2.0) + max(0.0, 2.5 - ease) * 3.0 + (1.0 if reps == 0 else 0.0)
        scores.append(score)
        scored_cards.append((score, card))

    threshold = _percentile(scores, 0.75)
    hard_cards = [item for item in scored_cards if item[0] >= threshold]
    hard_cards.sort(key=lambda x: x[0], reverse=True)

    top_decks = sorted(deck_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:6]

    lines = [
        f"Total flashcards: {len(cards)}",
        f"Due now: {due_count}",
        "Top decks:",
    ]
    for deck, stats in top_decks:
        count = int(stats["count"])
        due = int(stats["due"])
        avg_ease = stats["ease_sum"] / max(1, count)
        avg_lapses = stats["lapses_sum"] / max(1, count)
        lines.append(f"- {deck}: {count} cards, {due} due, avg ease {avg_ease:.2f}, avg lapses {avg_lapses:.2f}")

    if hard_cards:
        lines.append("Hardest cards (top 10):")
        for score, card in hard_cards[:10]:
            deck = _short(card.get("deck", "Personal"), 40)
            front = _short(card.get("front", ""), 70)
            lapses = _safe_int(card.get("lapses", 0))
            ease = _safe_float(card.get("ease", 2.5), 2.5)
            lines.append(f"- [{deck}] {front} (lapses {lapses}, ease {ease:.2f}, score {score:.2f})")
    else:
        lines.append("No unusually hard cards detected.")

    return "\n".join(lines)


@mcp.tool()
def get_pomodoro_stats() -> str:
    """Pomodoro summary: today, total, and configuration."""
    data, err = load_data()
    if err:
        return err

    sessions = _as_list(data, "cf_sessions")
    state = _as_dict(data, "cf_pomodoro_state")
    today = _today_iso()

    total_count = 0
    total_minutes = 0
    today_count = 0
    today_minutes = 0
    last_session: Optional[datetime] = None

    for session in sessions:
        if not isinstance(session, dict):
            continue
        raw_type = str(session.get("type", "")).lower()
        if raw_type in ("pomodoro", "pomo", "pomodoro_session"):
            total_count += 1
            minutes = _safe_int(session.get("minutes", 0))
            total_minutes += minutes
            if str(session.get("date", "")) == today:
                today_count += 1
                today_minutes += minutes
            ts = _datetime_from_any(session.get("timestamp") or session.get("ts") or session.get("date"))
            if ts and (last_session is None or ts > last_session):
                last_session = ts

    pomo_len = _safe_int(state.get("pomoLen", 25), 25)
    break_len = _safe_int(state.get("breakLen", 5), 5)
    long_break_len = _safe_int(state.get("longBreakLen", 15), 15)
    pomos_per_long = _safe_int(state.get("pomosPerLongBreak", 4), 4)
    is_running = bool(state.get("isRunning"))
    is_break = bool(state.get("isBreak"))

    lines = [
        f"Total pomodoros: {total_count} ({total_minutes} min)",
        f"Pomodoros today: {today_count} ({today_minutes} min)",
        f"Config: focus {pomo_len}m, break {break_len}m, long {long_break_len}m every {pomos_per_long} pomos",
        f"State: {'running' if is_running else 'paused'} ({'break' if is_break else 'focus'})",
    ]
    if last_session:
        lines.append(f"Last session: {last_session.isoformat(timespec='minutes')}")

    return "\n".join(lines)


@mcp.tool()
def get_today_schedule() -> str:
    """Today's events and weekly schedule blocks."""
    data, err = load_data()
    if err:
        return err

    events = _as_list(data, "cf_events")
    schedule_entries = _as_list(data, "cf_schedule")

    today = date.today()
    today_iso = today.isoformat()
    day_of_week = today.weekday()  # Monday=0

    today_events = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        start_date = _date_from_string(ev.get("start"))
        end_date = _date_from_string(ev.get("end"))
        if not start_date or not end_date:
            continue
        if start_date <= today <= end_date:
            today_events.append(ev)

    def event_sort_key(ev: Dict[str, Any]) -> str:
        start = ev.get("start")
        if isinstance(start, str) and len(start) >= 16:
            return start
        if isinstance(start, str) and len(start) >= 10:
            return start + "T00:00"
        return "9999-12-31T00:00"

    today_events.sort(key=event_sort_key)

    today_schedule = [
        entry
        for entry in schedule_entries
        if isinstance(entry, dict) and _safe_int(entry.get("day", -1)) == day_of_week
    ]
    today_schedule.sort(key=lambda x: str(x.get("startTime", "")))

    if not today_events and not today_schedule:
        return f"No events or schedule blocks for today ({today_iso})."

    lines = [f"Today's schedule ({today_iso}):"]
    if today_events:
        lines.append("Events:")
        for ev in today_events:
            title = _short(ev.get("title", "Event"), 80)
            start = ev.get("start", "")
            end = ev.get("end", "")
            course = _short(ev.get("course", ""), 40)
            location = _short(ev.get("location", ""), 40)
            extra = ""
            if course:
                extra += f" | {course}"
            if location:
                extra += f" | {location}"
            lines.append(f"- {title} ({start} -> {end}){extra}")

    if today_schedule:
        if today_events:
            lines.append("")
        lines.append("Weekly schedule:")
        for entry in today_schedule:
            title = _short(entry.get("title", "Block"), 60)
            start = entry.get("startTime", "")
            end = entry.get("endTime", "")
            course = _short(entry.get("course", ""), 40)
            location = _short(entry.get("location", ""), 40)
            extra = ""
            if course:
                extra += f" | {course}"
            if location:
                extra += f" | {location}"
            lines.append(f"- {start}-{end} {title}{extra}")

    return "\n".join(lines)


@mcp.tool()
def get_daily_missions() -> str:
    """Daily missions with progress and boss status."""
    data, err = load_data()
    if err:
        return err

    missions_state = _as_dict(data, "cf_missions_v2")
    missions = missions_state.get("missions") if isinstance(missions_state.get("missions"), list) else []
    missions_date = missions_state.get("date") if isinstance(missions_state.get("date"), str) else ""
    boss = missions_state.get("boss") if isinstance(missions_state.get("boss"), dict) else {}
    chest = missions_state.get("chest") if isinstance(missions_state.get("chest"), dict) else {}

    if not missions:
        return "No daily missions available."

    lines = ["Daily missions:"]
    if missions_date:
        lines.append(f"Date: {missions_date}")

    for mission in missions:
        if not isinstance(mission, dict):
            continue
        meta = mission.get("meta") if isinstance(mission.get("meta"), dict) else {}
        title = _short(meta.get("title") or meta.get("label") or mission.get("type", "Mission"), 80)
        tier = str(mission.get("tier", "")) or "normal"
        current = _safe_int(mission.get("current", 0))
        target = _safe_int(mission.get("target", 0))
        xp = _safe_int(meta.get("xp", 0))
        completed = bool(mission.get("completed"))
        claimed = bool(mission.get("claimed"))
        status = "claimed" if claimed else "complete" if completed else "in progress"
        lines.append(f"- [{tier}] {title} {current}/{target} | XP {xp} | {status}")

    if boss:
        level = _safe_int(boss.get("level", 1))
        hp = _safe_int(boss.get("hp", 0))
        max_hp = _safe_int(boss.get("maxHp", 0))
        defeated = bool(boss.get("defeated"))
        boss_type = _short(boss.get("typeId", ""), 30)
        lines.append("Boss:")
        lines.append(
            f"- type {boss_type or 'N/A'}, level {level}, HP {hp}/{max_hp}, defeated: {'yes' if defeated else 'no'}"
        )

    if chest:
        ready = bool(chest.get("ready"))
        opened = bool(chest.get("opened"))
        lines.append("Chest:")
        lines.append(f"- ready: {'yes' if ready else 'no'}, opened: {'yes' if opened else 'no'}")

    return "\n".join(lines)


@mcp.tool()
def get_full_summary() -> str:
    """High-level summary to use as a first call."""
    data, err = load_data()
    if err:
        return err

    today = date.today()
    today_iso = today.isoformat()

    xp_ledger = _as_list(data, "cf_xp")
    total_xp = sum(_safe_int(entry.get("amount", entry.get("value", 0))) for entry in xp_ledger)
    level_data = _level_from_xp(total_xp)

    coins = _as_dict(data, "cf_coins")
    focus_coins = _safe_int(coins.get("focus", coins.get("coins", 0)))

    streak = _as_dict(data, "cf_streak")
    streak_days = _safe_int(streak.get("days", 0))
    max_days = _safe_int(streak.get("maxDays", 0))

    tasks = _as_list(data, "cf_tasks")
    todos = _as_list(data, "cf_todos")
    pending_tasks = [t for t in tasks if isinstance(t, dict) and not t.get("done")]
    pending_todos = [t for t in todos if isinstance(t, dict) and not t.get("done")]

    cards = _as_list(data, "cf_cards")
    now = datetime.now()
    due_cards = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        due_dt = _datetime_from_any(card.get("due"))
        if due_dt is None or due_dt <= now:
            due_cards += 1

    sessions = _as_list(data, "cf_sessions")
    today_pomos = 0
    today_minutes = 0
    for session in sessions:
        if not isinstance(session, dict):
            continue
        raw_type = str(session.get("type", "")).lower()
        if raw_type in ("pomodoro", "pomo", "pomodoro_session"):
            if str(session.get("date", "")) == today_iso:
                today_pomos += 1
                today_minutes += _safe_int(session.get("minutes", 0))

    missions_state = _as_dict(data, "cf_missions_v2")
    missions = missions_state.get("missions") if isinstance(missions_state.get("missions"), list) else []
    completed_missions = 0
    for m in missions:
        if isinstance(m, dict) and m.get("completed"):
            completed_missions += 1

    events = _as_list(data, "cf_events")
    schedule_entries = _as_list(data, "cf_schedule")
    day_of_week = today.weekday()
    today_events = 0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        start_date = _date_from_string(ev.get("start"))
        end_date = _date_from_string(ev.get("end"))
        if start_date and end_date and start_date <= today <= end_date:
            today_events += 1
    today_schedule = sum(1 for e in schedule_entries if isinstance(e, dict) and _safe_int(e.get("day", -1)) == day_of_week)

    lines = [
        "Study Hub Summary:",
        f"- Date: {today_iso}",
        f"- Level {level_data['level']} | XP {total_xp} ({level_data['into']}/{level_data['need']})",
        f"- Focus Coins: {focus_coins}",
        f"- Streak: {streak_days} days (max {max_days})",
        f"- Pending tasks: {len(pending_tasks)} | Pending todos: {len(pending_todos)}",
        f"- Flashcards: {len(cards)} total, {due_cards} due",
        f"- Pomodoros today: {today_pomos} ({today_minutes} min)",
        f"- Missions completed: {completed_missions}/{len(missions) if missions else 0}",
        f"- Schedule today: {today_events} events, {today_schedule} blocks",
    ]

    return "\n".join(lines)


# --- MCP PROMPTS ---

@mcp.prompt()
def plan_my_day() -> str:
    """Create a personalized study plan for today based on pending tasks and schedule."""
    return (
        "Please use the `get_full_summary`, `get_today_schedule`, and `get_pending_tasks` tools "
        "to analyze my current workload. "
        "Act as an expert study coach and create a realistic, step-by-step study plan for today. "
        "Prioritize high-priority tasks and fit them around my existing schedule."
    )


@mcp.prompt()
def review_my_flashcards() -> str:
    """Analyze flashcard performance and suggest a study strategy."""
    return (
        "Please use the `get_flashcard_analysis` and `get_daily_missions` tools. "
        "Identify the topics I am struggling with the most. "
        "Act as a strict but encouraging tutor, tell me which deck I need to focus on today, "
        "and remind me of the rewards I will get if I complete my daily missions."
    )


if __name__ == "__main__":
    mcp.run()
