#!/usr/bin/env python3
"""Небольшая проверка структуры репозитория кампании.

Скрипт использует только стандартную библиотеку Python. Это не полноценный
Markdown- или YAML-парсер: он намеренно проверяет лишь простые соглашения
данного шаблона и не изменяет файлы.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = (
    "README.md",
    "MANIFEST.md",
    "CURRENT.md",
    ".gitignore",
    "chatgpt-project/SETUP_AND_PROMPTS.md",
    "campaign/premises.md",
    "campaign/established-facts.md",
    "campaign/timeline.md",
    "campaign/open-threads.md",
    "campaign/clocks.md",
    "party/party.md",
    "party/character-template.md",
    "npcs/index.md",
    "npcs/npc-template.md",
    "locations/index.md",
    "locations/location-template.md",
    "rules/precedence.md",
    "rules/house-rules.md",
    "rules/rulings.md",
    "rules/quick-reference.md",
    "gm/secrets.md",
    "gm/factions.md",
    "gm/future-events.md",
    "gm/module-overrides.md",
    "journal/README.md",
    "journal/entry-template.md",
    "checkpoints/README.md",
    "checkpoints/checkpoint-template.yaml",
    "archive/README.md",
    "templates/README.md",
    "templates/reset-paths.txt",
    "templates/CURRENT.md",
    "scripts/reset_campaign.sh",
    "scripts/validate_repo.py",
)

ENTITY_TEMPLATES = (
    "party/character-template.md",
    "npcs/npc-template.md",
    "locations/location-template.md",
)

# Эти разделы нужны для восстановления минимального актуального снимка.
REQUIRED_SECTIONS = {
    "CURRENT.md": (
        "Метаданные кампании",
        "Непрерывность",
        "Внутриигровая дата и время",
        "Текущее местоположение",
        "Присутствующие персонажи",
        "Непосредственная ситуация",
        "Активные угрозы",
        "Активные часы",
        "Важные ресурсы группы",
        "Текущие состояния персонажей",
        "Ожидающие решения",
        "Недавно установленные факты",
        "Файлы последнего checkpoint",
        "Следующая рекомендуемая точка загрузки",
    ),
    "party/character-template.md": (
        "Концепция",
        "Игровые показатели",
        "Здоровье и состояния",
        "Способности",
        "Инвентарь",
        "Расходуемые ресурсы",
        "Отношения",
        "Цели",
        "Знания и важные разговоры",
        "Известные секреты",
        "Заметки по развитию",
        "История изменений",
    ),
    "npcs/npc-template.md": (
        "Краткое описание",
        "Внешний вид",
        "Роль",
        "Мотивация",
        "Текущая цель",
        "Ресурсы",
        "Игровые показатели",
        "Отношение к персонажам",
        "Что NPC знает",
        "Что о нём знают игроки",
        "Секреты",
        "Текущее состояние",
        "История изменений",
    ),
    "locations/location-template.md": (
        "Краткое описание",
        "Текущее состояние",
        "Выходы и связи",
        "Находящиеся здесь сущности",
        "Опасности",
        "Ресурсы",
        "Доступные действия",
        "Что известно игрокам",
        "Секреты ведущего",
        "Изменения относительно исходного приключения",
        "История изменений",
    ),
}

TEXT_NAMES = {".gitignore"}
TEXT_SUFFIXES = {".md", ".py", ".txt", ".yaml", ".yml", ".json"}
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$")
ID_LINE_RE = re.compile(r"^\s*id\s*:\s*(.*?)\s*$", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CHECKPOINT_RE = re.compile(r"^cp-(\d{4})$")
SCENE_RE = re.compile(r"^scene-(\d{4})$")
JOURNAL_RE = re.compile(r"^journal\.entry-(\d{4})$")
EVENT_RE = re.compile(r"^event-\d{3,}$")
LEGACY_SESSION_RE = re.compile(
    r"sessions/|session-\d{3,4}|сесси",
    re.IGNORECASE,
)
PROJECT_ATTACHMENT_TERMS = (
    "PDF правил",
    "PDF приключения",
    "attachment",
)
PLAY_CONTRACT = "module-play/v1"


def repository_text_files() -> list[Path]:
    """Возвращает рабочие текстовые файлы, исключая Git и копию шаблона."""
    result: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if (
            not path.is_file()
            or ".git" in path.parts
            or "templates" in path.parts
            or (
                path.parent == REPO_ROOT
                and path.name.startswith(("plan-by-", "review-by-"))
            )
        ):
            continue
        if path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES:
            result.append(path)
    return sorted(result)


def display(path: Path) -> str:
    """Показывает путь относительно корня, если это возможно."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def load_texts(
    paths: list[Path], errors: list[str]
) -> dict[Path, str]:
    """Читает UTF-8 и отдельно сообщает о неверной кодировке и CRLF."""
    texts: dict[Path, str] = {}
    for path in paths:
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{display(path)}: файл не является корректным UTF-8 ({exc})")
            continue
        if b"\r\n" in raw or b"\r" in raw:
            errors.append(f"{display(path)}: обнаружены окончания строк CR/CRLF, нужны LF")
        texts[path] = text
    return texts


def check_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (REPO_ROOT / relative).is_file():
            errors.append(f"{relative}: отсутствует обязательный файл")


def check_reset_template(errors: list[str]) -> None:
    """Проверяет, что каждый разрешённый reset-путь имеет источник."""
    list_path = REPO_ROOT / "templates/reset-paths.txt"
    if not list_path.is_file():
        return
    try:
        raw_paths = list_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        errors.append(f"templates/reset-paths.txt: неверный UTF-8 ({exc})")
        return

    reset_paths = [
        item.strip()
        for item in raw_paths
        if item.strip() and not item.lstrip().startswith("#")
    ]
    if len(reset_paths) != len(set(reset_paths)):
        errors.append("templates/reset-paths.txt: обнаружены повторяющиеся пути")

    required_reset_paths = {
        "CURRENT.md",
        "archive",
        "campaign",
        "checkpoints",
        "gm",
        "journal",
        "locations",
        "npcs",
        "party",
        "rules",
    }
    missing = sorted(required_reset_paths - set(reset_paths))
    unexpected = sorted(set(reset_paths) - required_reset_paths)
    if missing:
        errors.append(
            "templates/reset-paths.txt: отсутствуют обязательные пути: "
            + ", ".join(missing)
        )
    if unexpected:
        errors.append(
            "templates/reset-paths.txt: неразрешённые пути: "
            + ", ".join(unexpected)
        )

    for relative in reset_paths:
        if (
            relative.startswith("/")
            or relative in {".", ".."}
            or ".." in Path(relative).parts
        ):
            errors.append(
                f"templates/reset-paths.txt: небезопасный путь '{relative}'"
            )
            continue
        if not (REPO_ROOT / "templates" / relative).exists():
            errors.append(
                f"templates/{relative}: отсутствует источник для сброса"
            )


def front_matter(text: str) -> dict[str, str] | None:
    """Разбирает только строки вида key: value в начальном front matter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return None


def top_level_yaml(text: str) -> dict[str, str]:
    """Разбирает скаляры верхнего уровня простого checkpoint YAML."""
    data: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return data


def nested_yaml_scalar(text: str, section: str, key: str) -> str | None:
    """Находит скаляр первого уровня вложенности в простом YAML."""
    lines = text.splitlines()
    in_section = False
    section_re = re.compile(rf"^{re.escape(section)}:\s*$")
    key_re = re.compile(rf"^  {re.escape(key)}:\s*(.*?)\s*$")
    for line in lines:
        if section_re.match(line):
            in_section = True
            continue
        if in_section and line and not line[0].isspace():
            return None
        if in_section:
            match = key_re.match(line)
            if match:
                return match.group(1).strip().strip("\"'")
    return None


def optional_scalar(value: str | None) -> str | None:
    """Normalizes the empty/null spellings used by front matter and YAML."""
    if value is None or value.strip() in {"", "null", "~"}:
        return None
    return value.strip()


def yaml_section_lines(text: str, section: str) -> list[str]:
    """Возвращает строки простого верхнеуровневого раздела YAML."""
    lines = text.splitlines()
    section_re = re.compile(rf"^{re.escape(section)}:\s*$")
    in_section = False
    result: list[str] = []
    for line in lines:
        if section_re.match(line):
            in_section = True
            continue
        if in_section and line and not line[0].isspace():
            break
        if in_section:
            result.append(line)
    return result


def yaml_mapping_keys(lines: list[str], indent: int) -> set[str]:
    """Собирает ключи mapping на указанном уровне отступа."""
    key_re = re.compile(rf"^ {{{indent}}}([a-zA-Z0-9_]+):(?:\s|$)")
    return {
        match.group(1)
        for line in lines
        if (match := key_re.match(line)) is not None
    }


def yaml_list_mappings(lines: list[str], indent: int) -> list[dict[str, str]]:
    """Разбирает список плоских mapping с простыми скалярными значениями."""
    item_re = re.compile(
        rf"^ {{{indent}}}-\s+([a-zA-Z0-9_]+):\s*(.*?)\s*$"
    )
    field_re = re.compile(
        rf"^ {{{indent + 2}}}([a-zA-Z0-9_]+):\s*(.*?)\s*$"
    )
    child_re = re.compile(rf"^ {{{indent + 4}}}-\s+(.*?)\s*$")
    result: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    current_list_key: str | None = None
    for line in lines:
        item_match = item_re.match(line)
        if item_match:
            current = {
                item_match.group(1): item_match.group(2).strip().strip("\"'")
            }
            result.append(current)
            current_list_key = None
            continue
        field_match = field_re.match(line)
        if field_match and current is not None:
            key = field_match.group(1)
            value = field_match.group(2).strip().strip("\"'")
            current[key] = value
            current_list_key = key if not value else None
            continue
        child_match = child_re.match(line)
        if (
            child_match
            and current is not None
            and current_list_key is not None
        ):
            value = child_match.group(1).strip().strip("\"'")
            previous = current[current_list_key]
            current[current_list_key] = (
                f"{previous}\n{value}" if previous else f"\n{value}"
            )
    return result


def yaml_nested_list_lines(
    lines: list[str], key: str, indent: int = 2
) -> list[str]:
    """Возвращает тело вложенного списка до следующего соседнего ключа."""
    key_re = re.compile(rf"^ {{{indent}}}{re.escape(key)}:\s*$")
    sibling_re = re.compile(rf"^ {{{indent}}}[a-zA-Z0-9_]+:")
    in_list = False
    result: list[str] = []
    for line in lines:
        if key_re.match(line):
            in_list = True
            continue
        if in_list and sibling_re.match(line):
            break
        if in_list:
            result.append(line)
    return result


def check_delta_checkpoint_payload(
    path: Path, text: str, known_refs: set[str], errors: list[str]
) -> None:
    """Проверяет обязательный контракт checkpoint-дельты."""
    data = top_level_yaml(text)
    if data.get("kind") != "delta":
        return

    current_scene_lines = yaml_section_lines(text, "current_scene")
    current_scene_keys = yaml_mapping_keys(current_scene_lines, 2)
    required_scene_keys = {
        "fiction_time",
        "location",
        "module_place_id",
        "present",
        "situation",
        "active_threats",
        "key_resources",
        "pending_decisions",
    }
    missing_scene_keys = sorted(required_scene_keys - current_scene_keys)
    if missing_scene_keys:
        errors.append(
            f"{display(path)}: current_scene не содержит обязательные поля: "
            + ", ".join(missing_scene_keys)
        )

    journal_lines = yaml_section_lines(text, "journal_append")
    journal_keys = yaml_mapping_keys(journal_lines, 2)
    if "events" not in journal_keys:
        errors.append(
            f"{display(path)}: journal_append не содержит обязательное поле events"
        )
    event_lines = yaml_nested_list_lines(journal_lines, "events")
    events = yaml_list_mappings(event_lines, 4)
    raw_event_items = sum(
        1 for line in event_lines if re.match(r"^ {4}-\s+", line)
    )
    if raw_event_items != len(events):
        errors.append(
            f"{display(path)}: каждый элемент journal_append.events "
            "должен быть объектом с id и summary"
        )
    event_ids: set[str] = set()
    allowed_event_types = {"action", "dialogue", "discovery"}
    for index, event in enumerate(events, start=1):
        event_id = event.get("id", "")
        if not EVENT_RE.fullmatch(event_id):
            errors.append(
                f"{display(path)}: journal_append.events[{index}].id "
                "должен иметь вид event-NNN"
            )
        elif event_id in event_ids:
            errors.append(
                f"{display(path)}: повторяющийся event ID '{event_id}'"
            )
        else:
            event_ids.add(event_id)
        if not event.get("summary"):
            errors.append(
                f"{display(path)}: journal_append.events[{index}] "
                "не содержит summary"
            )
        event_type = event.get("type", "")
        if event_type not in allowed_event_types:
            errors.append(
                f"{display(path)}: journal_append.events[{index}].type "
                f"'{event_type}' не входит в action, dialogue, discovery"
            )
        if not event.get("fiction_time"):
            errors.append(
                f"{display(path)}: journal_append.events[{index}] "
                "не содержит fiction_time"
            )
        if event_type == "dialogue":
            missing_dialogue = []
            speaker = event.get("speaker", "")
            if not speaker:
                missing_dialogue.append("speaker")
            elif not ID_RE.fullmatch(speaker):
                errors.append(
                    f"{display(path)}: dialogue event {event_id or index} "
                    f"имеет неверный speaker '{speaker}'"
                )
            recipients = event.get("recipients", "")
            inline_recipients = (
                recipients.startswith("[")
                and recipients.endswith("]")
                and recipients != "[]"
            )
            if not recipients.startswith("\n") and not inline_recipients:
                missing_dialogue.append("recipients")
            if missing_dialogue:
                errors.append(
                    f"{display(path)}: dialogue event {event_id or index} "
                    "не содержит поля: " + ", ".join(missing_dialogue)
                )

    change_lines = yaml_section_lines(text, "changes")
    changes = yaml_list_mappings(change_lines, 2)
    raw_change_items = sum(
        1 for line in change_lines if re.match(r"^ {2}-\s+", line)
    )
    if raw_change_items != len(changes):
        errors.append(
            f"{display(path)}: каждый элемент changes должен быть объектом"
        )
    allowed_operations = {"set", "add", "remove", "move"}
    common_fields = {"operation", "target", "reason", "source_event"}
    for index, change in enumerate(changes, start=1):
        missing = sorted(
            key for key in common_fields if not change.get(key)
        )
        operation = change.get("operation", "")
        if operation not in allowed_operations:
            errors.append(
                f"{display(path)}: changes[{index}].operation "
                f"'{operation}' не входит в set, add, remove, move"
            )
        if operation in {"set", "move"}:
            missing.extend(
                key for key in ("from", "to") if key not in change
            )
        elif operation in {"add", "remove"} and "value" not in change:
            missing.append("value")
        if missing:
            errors.append(
                f"{display(path)}: changes[{index}] не содержит поля: "
                + ", ".join(sorted(set(missing)))
            )

        source_event = change.get("source_event", "")
        if source_event and source_event not in event_ids:
            errors.append(
                f"{display(path)}: changes[{index}].source_event "
                f"'{source_event}' не найден в journal_append.events"
            )

    resource_lines = yaml_section_lines(text, "resource_changes")
    resources = yaml_list_mappings(resource_lines, 2)
    raw_resource_items = sum(
        1 for line in resource_lines if re.match(r"^ {2}-\s+", line)
    )
    if raw_resource_items != len(resources):
        errors.append(
            f"{display(path)}: каждый элемент resource_changes "
            "должен быть объектом"
        )
    allowed_resource_operations = {
        "add",
        "update",
        "transfer",
        "consume",
        "remove",
    }
    required_resource_fields = {
        "id",
        "operation",
        "name",
        "quantity_before",
        "quantity_after",
        "holder_before",
        "holder_after",
        "condition_before",
        "condition_after",
        "capabilities",
        "limitations",
        "maintenance",
        "load_limit",
        "noise",
        "light",
        "consumption",
        "source_event",
    }
    resource_ids: set[str] = set()
    null_values = {"", "null", "~"}
    for index, resource in enumerate(resources, start=1):
        missing = sorted(required_resource_fields - resource.keys())
        resource_id = resource.get("id", "")
        if not ID_RE.fullmatch(resource_id):
            errors.append(
                f"{display(path)}: resource_changes[{index}].id "
                f"'{resource_id}' имеет неверный формат"
            )
        elif resource_id in resource_ids:
            errors.append(
                f"{display(path)}: повторяющийся resource_changes.id "
                f"'{resource_id}'"
            )
        else:
            resource_ids.add(resource_id)

        operation = resource.get("operation", "")
        if operation not in allowed_resource_operations:
            errors.append(
                f"{display(path)}: resource_changes[{index}].operation "
                "должен быть add, update, transfer, consume или remove"
            )
        if not resource.get("name"):
            missing.append("name")
        if operation == "transfer":
            for key in ("holder_before", "holder_after"):
                if resource.get(key, "") in null_values:
                    errors.append(
                        f"{display(path)}: resource_changes[{index}].{key} "
                        "для transfer должен однозначно указывать держателя"
                    )
        if operation == "consume":
            for key in ("quantity_before", "quantity_after"):
                if resource.get(key, "") in null_values:
                    errors.append(
                        f"{display(path)}: resource_changes[{index}].{key} "
                        "для consume должен содержать количество или unknown"
                    )
        if missing:
            errors.append(
                f"{display(path)}: resource_changes[{index}] "
                "не содержит поля: " + ", ".join(sorted(set(missing)))
            )
        source_event = resource.get("source_event", "")
        if source_event and source_event not in event_ids:
            errors.append(
                f"{display(path)}: resource_changes[{index}].source_event "
                f"'{source_event}' не найден в journal_append.events"
            )

    new_facts = yaml_list_mappings(
        yaml_section_lines(text, "new_facts"), 2
    )
    fact_ids: set[str] = set()
    allowed_fact_kinds = {"established", "npc-claim", "rumor", "belief"}
    allowed_truth_statuses = {"confirmed", "unverified", "false", "mixed"}
    fact_fields = {
        "id",
        "kind",
        "content",
        "truth_status",
        "knowledge_level",
        "source_event",
    }
    for index, fact in enumerate(new_facts, start=1):
        missing = sorted(key for key in fact_fields if not fact.get(key))
        fact_id = fact.get("id", "")
        if fact_id and (
            not ID_RE.fullmatch(fact_id)
            or fact_id in fact_ids
            or fact_id in known_refs
        ):
            errors.append(
                f"{display(path)}: new_facts[{index}].id "
                f"'{fact_id}' некорректен или повторяется"
            )
        elif fact_id:
            fact_ids.add(fact_id)
        if fact.get("kind", "") not in allowed_fact_kinds:
            errors.append(
                f"{display(path)}: new_facts[{index}].kind должен быть "
                "established, npc-claim, rumor или belief"
            )
        if fact.get("truth_status", "") not in allowed_truth_statuses:
            errors.append(
                f"{display(path)}: new_facts[{index}].truth_status должен быть "
                "confirmed, unverified, false или mixed"
            )
        if missing:
            errors.append(
                f"{display(path)}: new_facts[{index}] не содержит поля: "
                + ", ".join(missing)
            )
        source_event = fact.get("source_event", "")
        if source_event and source_event not in event_ids:
            errors.append(
                f"{display(path)}: new_facts[{index}].source_event "
                f"'{source_event}' не найден в journal_append.events"
            )

    thread_changes = yaml_list_mappings(
        yaml_section_lines(text, "open_thread_changes"), 2
    )
    added_thread_ids: set[str] = set()
    allowed_thread_operations = {"add", "update", "close"}
    for index, thread in enumerate(thread_changes, start=1):
        operation = thread.get("operation", "")
        thread_id = thread.get("thread_id", "")
        missing = [
            key
            for key in ("operation", "thread_id", "source_event")
            if not thread.get(key)
        ]
        if operation not in allowed_thread_operations:
            errors.append(
                f"{display(path)}: open_thread_changes[{index}].operation "
                "должен быть add, update или close"
            )
        if not ID_RE.fullmatch(thread_id):
            errors.append(
                f"{display(path)}: open_thread_changes[{index}].thread_id "
                f"'{thread_id}' имеет неверный формат"
            )
        if operation == "add":
            missing.extend(
                key
                for key in ("title", "question", "status", "knowledge_level")
                if not thread.get(key)
            )
            if thread_id in known_refs or thread_id in added_thread_ids:
                errors.append(
                    f"{display(path)}: сюжетная линия '{thread_id}' уже существует"
                )
            elif thread_id:
                added_thread_ids.add(thread_id)
        elif operation == "update":
            if not thread.get("note"):
                missing.append("note")
            if thread_id not in known_refs and thread_id not in added_thread_ids:
                errors.append(
                    f"{display(path)}: обновляемая линия '{thread_id}' не найдена"
                )
        elif operation == "close":
            if not thread.get("resolution"):
                missing.append("resolution")
            if thread_id not in known_refs and thread_id not in added_thread_ids:
                errors.append(
                    f"{display(path)}: закрываемая линия '{thread_id}' не найдена"
                )
        if missing:
            errors.append(
                f"{display(path)}: open_thread_changes[{index}] не содержит поля: "
                + ", ".join(sorted(set(missing)))
            )
        source_event = thread.get("source_event", "")
        if source_event and source_event not in event_ids:
            errors.append(
                f"{display(path)}: open_thread_changes[{index}].source_event "
                f"'{source_event}' не найден в journal_append.events"
            )

    available_knowledge_refs = known_refs | fact_ids | added_thread_ids
    for index, thread in enumerate(thread_changes, start=1):
        raw_related_facts = thread.get("related_facts", "")
        related_facts = [
            value
            for value in raw_related_facts.splitlines()
            if value and value != "[]"
        ]
        for fact_ref in related_facts:
            if fact_ref not in available_knowledge_refs:
                errors.append(
                    f"{display(path)}: open_thread_changes[{index}] "
                    f"ссылается на неизвестный факт '{fact_ref}'"
                )

    knowledge_changes = yaml_list_mappings(
        yaml_section_lines(text, "knowledge_changes"), 2
    )
    allowed_knowledge_operations = {"add", "update", "remove"}
    knowledge_fields = {
        "operation",
        "subject",
        "knowledge_ref",
        "summary",
        "source_event",
    }
    for index, knowledge in enumerate(knowledge_changes, start=1):
        missing = sorted(
            key for key in knowledge_fields if not knowledge.get(key)
        )
        operation = knowledge.get("operation", "")
        if operation not in allowed_knowledge_operations:
            errors.append(
                f"{display(path)}: knowledge_changes[{index}].operation "
                "должен быть add, update или remove"
            )
        subject = knowledge.get("subject", "")
        if subject != "party" and not ID_RE.fullmatch(subject):
            errors.append(
                f"{display(path)}: knowledge_changes[{index}].subject "
                f"'{subject}' должен быть ID сущности или party"
            )
        knowledge_ref = knowledge.get("knowledge_ref", "")
        if knowledge_ref and knowledge_ref not in available_knowledge_refs:
            errors.append(
                f"{display(path)}: knowledge_changes[{index}].knowledge_ref "
                f"'{knowledge_ref}' не найден"
            )
        if missing:
            errors.append(
                f"{display(path)}: knowledge_changes[{index}] не содержит поля: "
                + ", ".join(missing)
            )
        source_event = knowledge.get("source_event", "")
        if source_event and source_event not in event_ids:
            errors.append(
                f"{display(path)}: knowledge_changes[{index}].source_event "
                f"'{source_event}' не найден в journal_append.events"
            )

    for index, event in enumerate(events, start=1):
        raw_refs = event.get("knowledge_refs", "")
        knowledge_refs = [
            value for value in raw_refs.splitlines() if value and value != "[]"
        ]
        for knowledge_ref in knowledge_refs:
            if knowledge_ref not in available_knowledge_refs:
                errors.append(
                    f"{display(path)}: journal_append.events[{index}] "
                    f"ссылается на неизвестное знание '{knowledge_ref}'"
                )


def check_entity_front_matter(
    texts: dict[Path, str], errors: list[str]
) -> None:
    required_keys = {"id", "type", "name", "status", "location",
                     "knowledge_level", "last_updated"}
    for relative in ENTITY_TEMPLATES:
        path = REPO_ROOT / relative
        text = texts.get(path)
        if text is None:
            continue
        data = front_matter(text)
        if data is None:
            errors.append(f"{relative}: нет корректного YAML front matter в начале файла")
            continue
        missing = sorted(required_keys - data.keys())
        if missing:
            errors.append(
                f"{relative}: во front matter отсутствуют ключи: {', '.join(missing)}"
            )


def check_entity_checkpoint_ids(
    texts: dict[Path, str], errors: list[str]
) -> None:
    """Проверяет last_updated в актуальных файлах сущностей."""
    patterns = (
        "party/character-*.md",
        "npcs/*.md",
        "locations/*.md",
    )
    for pattern in patterns:
        for path in REPO_ROOT.glob(pattern):
            text = texts.get(path)
            if text is None:
                continue
            data = front_matter(text)
            if data is None or "last_updated" not in data:
                continue
            value = data["last_updated"]
            if not CHECKPOINT_RE.fullmatch(value):
                errors.append(
                    f"{display(path)}: last_updated '{value}' должен иметь вид cp-NNNN"
                )


def check_continuity(
    texts: dict[Path, str], errors: list[str]
) -> None:
    """Проверяет указатели CURRENT и согласованность активного журнала."""
    current_path = REPO_ROOT / "CURRENT.md"
    text = texts.get(current_path)
    if text is None:
        return
    data = front_matter(text)
    if data is None:
        errors.append("CURRENT.md: нет корректного YAML front matter")
        return

    required = {
        "checkpoint_id",
        "active_scene_id",
        "active_journal_id",
        "campaign_status",
        "last_activity_at",
    }
    missing = sorted(required - data.keys())
    if missing:
        errors.append(
            "CURRENT.md: во front matter отсутствуют ключи: "
            + ", ".join(missing)
        )
        return

    checkpoint_id = data["checkpoint_id"]
    scene_id = data["active_scene_id"]
    journal_id = data["active_journal_id"]
    campaign_status = data["campaign_status"]

    if campaign_status == "preparation":
        for key in ("checkpoint_id", "active_scene_id", "active_journal_id"):
            if data[key] not in {"", "null", "~"}:
                errors.append(
                    f"CURRENT.md: в состоянии preparation поле {key} "
                    "должно быть пустым"
                )
        return

    if not CHECKPOINT_RE.fullmatch(checkpoint_id):
        errors.append(
            f"CURRENT.md: checkpoint_id '{checkpoint_id}' должен иметь вид cp-NNNN"
        )
    if not SCENE_RE.fullmatch(scene_id):
        errors.append(
            f"CURRENT.md: active_scene_id '{scene_id}' должен иметь вид scene-NNNN"
        )
    journal_match = JOURNAL_RE.fullmatch(journal_id)
    if not journal_match:
        errors.append(
            "CURRENT.md: active_journal_id "
            f"'{journal_id}' должен иметь вид journal.entry-NNNN"
        )
        return

    checkpoint_path = REPO_ROOT / "checkpoints" / f"{checkpoint_id}.yaml"
    if not checkpoint_path.is_file():
        errors.append(
            f"CURRENT.md: checkpoint_id ссылается на отсутствующий "
            f"{display(checkpoint_path)}"
        )

    journal_path = (
        REPO_ROOT / "journal" / f"entry-{journal_match.group(1)}.md"
    )
    journal_text = texts.get(journal_path)
    if journal_text is None:
        errors.append(
            f"CURRENT.md: active_journal_id ссылается на отсутствующий "
            f"{display(journal_path)}"
        )
        return
    journal_data = front_matter(journal_text)
    if journal_data is None:
        errors.append(f"{display(journal_path)}: нет корректного YAML front matter")
        return
    if journal_data.get("id") != journal_id:
        errors.append(
            f"{display(journal_path)}: id не совпадает с CURRENT.active_journal_id"
        )
    if journal_data.get("status") != "open":
        errors.append(
            f"{display(journal_path)}: активная запись должна иметь status: open"
        )
    if journal_data.get("last_checkpoint") != checkpoint_id:
        errors.append(
            f"{display(journal_path)}: last_checkpoint должен быть {checkpoint_id}"
        )
    if scene_id not in journal_text:
        errors.append(
            f"{display(journal_path)}: активная сцена {scene_id} не найдена"
        )


def load_json_object(path: Path, label: str, errors: list[str]) -> dict | None:
    """Loads a JSON object and reports a repository-validation error."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label}: отсутствует файл {display(path)}")
        return None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: {display(path)} не является корректным JSON ({exc})")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: {display(path)} должен содержать JSON object")
        return None
    return value


def check_module_campaign_binding(
    texts: dict[Path, str], errors: list[str]
) -> None:
    """Validates the optional exact binding from campaign state to a place card."""
    current_path = REPO_ROOT / "CURRENT.md"
    current_text = texts.get(current_path)
    if current_text is None:
        return
    current = front_matter(current_text)
    if current is None:
        return

    module_id = optional_scalar(current.get("module_id"))
    module_place_id = optional_scalar(current.get("module_place_id"))
    if current.get("campaign_status") == "preparation":
        if module_id is not None or module_place_id is not None:
            errors.append(
                "CURRENT.md: в состоянии preparation поля module_id и "
                "module_place_id должны быть пустыми"
            )
        return
    if (module_id is None) != (module_place_id is None):
        errors.append(
            "CURRENT.md: module_id и module_place_id должны быть либо оба "
            "заполнены, либо оба пусты"
        )
        return
    if module_id is None:
        checkpoint_id = optional_scalar(current.get("checkpoint_id"))
        if checkpoint_id is not None:
            checkpoint_path = (
                REPO_ROOT / "checkpoints" / f"{checkpoint_id}.yaml"
            )
            checkpoint_text = texts.get(checkpoint_path)
            if checkpoint_text is not None:
                checkpoint_place_id = optional_scalar(
                    nested_yaml_scalar(
                        checkpoint_text, "current_scene", "module_place_id"
                    )
                )
                if checkpoint_place_id is not None:
                    errors.append(
                        f"{display(checkpoint_path)}: "
                        "current_scene.module_place_id заполнен, но "
                        "CURRENT.module_id и CURRENT.module_place_id пусты"
                    )
        return

    module_root = REPO_ROOT / "module"
    marker = load_json_object(
        module_root / "GENERATED_OUTPUT.json", "CURRENT.module_id", errors
    )
    if marker is None:
        return
    if marker.get("play_contract") != PLAY_CONTRACT:
        errors.append(
            "module/GENERATED_OUTPUT.json: play_contract должен быть "
            f"{PLAY_CONTRACT} для привязки кампании"
        )
    if marker.get("verification") != "verified":
        errors.append(
            "module/GENERATED_OUTPUT.json: verification должен быть verified "
            "для привязки кампании"
        )
    if marker.get("module_id") != module_id:
        errors.append(
            "CURRENT.md: module_id "
            f"'{module_id}' не совпадает с module/GENERATED_OUTPUT.json "
            f"('{marker.get('module_id')}')"
        )
    for relative in ("MODULE.md", "index.json"):
        path = module_root / relative
        if not path.is_file():
            errors.append(
                f"CURRENT.module_id: отсутствует обязательный файл "
                f"{display(path)}"
            )

    index = load_json_object(
        module_root / "index.json", "CURRENT.module_place_id", errors
    )
    if index is None:
        return
    records = index.get("records")
    if not isinstance(records, list):
        errors.append("module/index.json: records должен быть JSON array")
        return
    matches = [
        item
        for item in records
        if isinstance(item, dict) and item.get("id") == module_place_id
    ]
    if not matches:
        errors.append(
            f"CURRENT.md: module_place_id '{module_place_id}' "
            "не найден в module/index.json"
        )
        return
    if len(matches) != 1:
        errors.append(
            f"module/index.json: ID '{module_place_id}' встречается более одного раза"
        )
        return
    record = matches[0]
    if record.get("type") != "place":
        errors.append(
            f"CURRENT.md: module_place_id '{module_place_id}' разрешается "
            f"в тип '{record.get('type')}', ожидался place"
        )
        return
    card_relative = record.get("path")
    if (
        not isinstance(card_relative, str)
        or not card_relative
        or card_relative.startswith("/")
        or ".." in Path(card_relative).parts
    ):
        errors.append(
            f"module/index.json: место '{module_place_id}' содержит "
            "небезопасный или отсутствующий path"
        )
    elif not (module_root / card_relative).is_file():
        errors.append(
            f"CURRENT.md: карточка места '{module_place_id}' отсутствует: "
            f"{display(module_root / card_relative)}"
        )

    checkpoint_id = optional_scalar(current.get("checkpoint_id"))
    if checkpoint_id is None:
        return
    checkpoint_path = REPO_ROOT / "checkpoints" / f"{checkpoint_id}.yaml"
    checkpoint_text = texts.get(checkpoint_path)
    if checkpoint_text is None and checkpoint_path.is_file():
        try:
            checkpoint_text = checkpoint_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            checkpoint_text = None
    if checkpoint_text is None:
        return
    checkpoint_place_id = optional_scalar(
        nested_yaml_scalar(checkpoint_text, "current_scene", "module_place_id")
    )
    if checkpoint_place_id != module_place_id:
        errors.append(
            f"{display(checkpoint_path)}: current_scene.module_place_id "
            f"'{checkpoint_place_id}' не совпадает с CURRENT.module_place_id "
            f"'{module_place_id}'"
        )

    location_id = optional_scalar(
        nested_yaml_scalar(checkpoint_text, "current_scene", "location")
    )
    if location_id is None:
        return
    location_matches: list[tuple[Path, dict[str, str]]] = []
    for path in sorted((REPO_ROOT / "locations").glob("*.md")):
        text = texts.get(path)
        if text is None:
            continue
        data = front_matter(text)
        if data is not None and data.get("id") == location_id:
            location_matches.append((path, data))
    for path, data in location_matches:
        location_module_ref = optional_scalar(data.get("module_ref"))
        if location_module_ref is not None and location_module_ref != module_place_id:
            errors.append(
                f"{display(path)}: module_ref '{location_module_ref}' "
                f"не совпадает с CURRENT.module_place_id '{module_place_id}'"
            )


def module_override_ids(text: str) -> list[tuple[int, str]]:
    """Return populated target IDs from the overrides markdown table.

    The table is intentionally parsed without a Markdown dependency. Fenced
    examples are ignored so the documentation can show sample rows without
    turning them into campaign state.
    """
    in_fence = False
    table_started = False
    result: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first.casefold() == "id":
            table_started = True
            continue
        if not table_started or re.fullmatch(r":?-{3,}:?", first):
            continue
        target = first.strip().strip("`").strip().strip('"')
        if target and target not in {"-", "—", "null", "~"}:
            result.append((number, target))
    return result


def check_module_override_targets(
    texts: dict[Path, str], errors: list[str]
) -> None:
    """Validate populated override IDs against the immutable runtime module."""
    override_path = REPO_ROOT / "gm" / "module-overrides.md"
    override_text = texts.get(override_path)
    if override_text is None:
        return
    targets = module_override_ids(override_text)
    if not targets:
        return

    current_path = REPO_ROOT / "CURRENT.md"
    current_text = texts.get(current_path)
    current = front_matter(current_text) if current_text is not None else None
    module_id = optional_scalar(current.get("module_id")) if current else None
    if module_id is None:
        errors.append(
            "gm/module-overrides.md: populated override IDs cannot be checked "
            "without CURRENT.module_id and a verified runtime module"
        )
        return

    module_root = REPO_ROOT / "module"
    marker = load_json_object(
        module_root / "GENERATED_OUTPUT.json",
        "gm/module-overrides.md",
        errors,
    )
    if marker is None:
        return
    if marker.get("play_contract") != PLAY_CONTRACT:
        errors.append(
            "gm/module-overrides.md: cannot validate targets because "
            f"play_contract is not {PLAY_CONTRACT}"
        )
    if marker.get("verification") != "verified":
        errors.append(
            "gm/module-overrides.md: cannot validate targets because "
            "module verification is not verified"
        )
    if marker.get("module_id") != module_id:
        errors.append(
            "gm/module-overrides.md: cannot validate targets because "
            "CURRENT.module_id does not match the runtime module"
        )
    if (
        marker.get("play_contract") != PLAY_CONTRACT
        or marker.get("verification") != "verified"
        or marker.get("module_id") != module_id
    ):
        return

    index = load_json_object(
        module_root / "index.json", "gm/module-overrides.md", errors
    )
    if index is None:
        return
    records = index.get("records")
    if not isinstance(records, list):
        errors.append(
            "gm/module-overrides.md: module/index.json records must be a JSON array"
        )
        return
    record_ids = {
        item["id"]
        for item in records
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    unresolved = {target for _line, target in targets if target not in record_ids}
    topology_ids: set[str] = set()
    if unresolved:
        topology = load_json_object(
            module_root / "topology.yaml", "gm/module-overrides.md", errors
        )
        if topology is not None:
            nodes = topology.get("nodes")
            passages = topology.get("passages")
            if not isinstance(nodes, list):
                errors.append(
                    "gm/module-overrides.md: module/topology.yaml nodes must be "
                    "a JSON array"
                )
            else:
                topology_ids.update(
                    item["id"]
                    for item in nodes
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                )
            if not isinstance(passages, list):
                # A small compatibility allowance makes the diagnostic useful
                # for hand-authored synthetic modules while generated runtime
                # output uses the canonical `passages` key.
                passages = topology.get("edges")
            if not isinstance(passages, list):
                errors.append(
                    "gm/module-overrides.md: module/topology.yaml passages must "
                    "be a JSON array"
                )
            else:
                topology_ids.update(
                    item["id"]
                    for item in passages
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                )

    for line, target in targets:
        if target in record_ids or target in topology_ids:
            continue
        errors.append(
            f"gm/module-overrides.md:{line}: invalid target ID '{target}'; "
            "not found in module/index.json or module/topology.yaml "
            "nodes/passages"
        )


def check_checkpoint_chain(
    texts: dict[Path, str], errors: list[str]
) -> None:
    """Проверяет имена, базу и связь последнего checkpoint с CURRENT."""
    checkpoint_paths = sorted((REPO_ROOT / "checkpoints").glob("cp-*.yaml"))
    current_text = texts.get(REPO_ROOT / "CURRENT.md")
    current_data = front_matter(current_text) if current_text is not None else None
    is_preparation = (
        current_data is not None
        and current_data.get("campaign_status") == "preparation"
    )

    if not checkpoint_paths:
        if is_preparation:
            return
        errors.append("checkpoints/: не найдено ни одного применённого checkpoint")
        return
    if is_preparation:
        errors.append(
            "checkpoints/: в состоянии preparation не должно быть "
            "применённых checkpoint"
        )
        return

    parsed: list[tuple[int, str, str | None, Path, str]] = []
    seen: dict[str, Path] = {}
    known_refs: set[str] = set()
    reference_re = re.compile(
        r"(?<![a-zA-Z0-9])([a-z][a-z0-9]*(?:[.-][a-z0-9]+)+)"
    )
    for known_path, known_text in texts.items():
        if "checkpoints" in known_path.parts:
            continue
        known_refs.update(reference_re.findall(known_text))

    # Актуальные профильные файлы уже содержат ID, созданные применёнными
    # delta-checkpoint. Убираем их из исходного набора и добавляем обратно
    # после проверки породившего checkpoint, чтобы отличать корректно
    # применённую дельту от ссылки, существовавшей до неё.
    introduced_refs: set[str] = set()
    for checkpoint_path in checkpoint_paths:
        checkpoint_text = texts.get(checkpoint_path)
        if checkpoint_text is None:
            continue
        introduced_refs.update(
            item.get("id", "")
            for item in yaml_list_mappings(
                yaml_section_lines(checkpoint_text, "new_facts"), 2
            )
            if item.get("id")
        )
        introduced_refs.update(
            item.get("thread_id", "")
            for item in yaml_list_mappings(
                yaml_section_lines(checkpoint_text, "open_thread_changes"), 2
            )
            if item.get("operation") == "add" and item.get("thread_id")
        )
    known_refs.difference_update(introduced_refs)

    for path in checkpoint_paths:
        text = texts.get(path)
        if text is None:
            continue
        data = top_level_yaml(text)
        checkpoint_id = data.get("checkpoint_id", "")
        match = CHECKPOINT_RE.fullmatch(checkpoint_id)
        if not match:
            errors.append(
                f"{display(path)}: checkpoint_id должен иметь вид cp-NNNN"
            )
            continue
        if path.name != f"{checkpoint_id}.yaml":
            errors.append(
                f"{display(path)}: имя файла не совпадает с checkpoint_id"
            )
        if checkpoint_id in seen:
            errors.append(
                f"повторяющийся checkpoint_id '{checkpoint_id}': "
                f"{display(seen[checkpoint_id])}, {display(path)}"
            )
        seen[checkpoint_id] = path
        if data.get("schema") != "campaign-checkpoint/v1":
            errors.append(
                f"{display(path)}: schema должна быть campaign-checkpoint/v1"
            )
        kind = data.get("kind")
        if checkpoint_id == "cp-0001":
            if kind != "baseline":
                errors.append(
                    f"{display(path)}: cp-0001 должен иметь kind: baseline"
                )
        elif kind != "delta":
            errors.append(
                f"{display(path)}: checkpoint после cp-0001 должен иметь kind: delta"
            )
        check_delta_checkpoint_payload(path, text, known_refs, errors)
        known_refs.update(
            item.get("id", "")
            for item in yaml_list_mappings(
                yaml_section_lines(text, "new_facts"), 2
            )
            if item.get("id")
        )
        known_refs.update(
            item.get("thread_id", "")
            for item in yaml_list_mappings(
                yaml_section_lines(text, "open_thread_changes"), 2
            )
            if item.get("operation") == "add" and item.get("thread_id")
        )
        base_raw = data.get("base_checkpoint_id")
        base = None if base_raw in {None, "null", "~"} else base_raw
        parsed.append((int(match.group(1)), checkpoint_id, base, path, text))

    parsed.sort(key=lambda item: item[0])
    for index, (number, checkpoint_id, base, path, _text) in enumerate(parsed):
        if index == 0:
            if checkpoint_id != "cp-0001" or base is not None:
                errors.append(
                    f"{display(path)}: цепочка должна начинаться с cp-0001 "
                    "и base_checkpoint_id: null"
                )
            continue
        previous_number, previous_id, _base, _path, _previous_text = parsed[index - 1]
        if number != previous_number + 1:
            errors.append(
                f"{display(path)}: пропуск в нумерации после {previous_id}"
            )
        if base != previous_id:
            errors.append(
                f"{display(path)}: base_checkpoint_id должен быть {previous_id}"
            )

    if parsed and current_data is not None:
        latest_id = parsed[-1][1]
        if current_data.get("checkpoint_id") != latest_id:
            errors.append(
                f"CURRENT.md: checkpoint_id должен указывать на последний {latest_id}"
            )
        latest_text = parsed[-1][4]
        expected_journal = nested_yaml_scalar(
            latest_text, "continuity", "journal_entry_id"
        )
        expected_scene = nested_yaml_scalar(latest_text, "continuity", "scene_id")
        if expected_journal != current_data.get("active_journal_id"):
            errors.append(
                f"checkpoints/{latest_id}.yaml: continuity.journal_entry_id "
                "не совпадает с CURRENT.md"
            )
        if expected_scene != current_data.get("active_scene_id"):
            errors.append(
                f"checkpoints/{latest_id}.yaml: continuity.scene_id "
                "не совпадает с CURRENT.md"
            )


def check_legacy_journal_references(
    texts: dict[Path, str], errors: list[str]
) -> None:
    """Не допускает рабочие ссылки на прежнюю календарную структуру."""
    for path, text in texts.items():
        if path.suffix.lower() != ".md":
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if LEGACY_SESSION_RE.search(line):
                errors.append(
                    f"{display(path)}:{line_number}: активная ссылка "
                    "на прежнюю календарную структуру журналов"
                )


def check_project_attachment_instructions(
    texts: dict[Path, str], errors: list[str]
) -> None:
    """Требует явной инструкции добавить книги в Project как attachments."""
    path = REPO_ROOT / "chatgpt-project/SETUP_AND_PROMPTS.md"
    text = texts.get(path)
    if text is None:
        return
    for term in PROJECT_ATTACHMENT_TERMS:
        if term not in text:
            errors.append(
                f"{display(path)}: нет обязательного упоминания '{term}'"
            )


def normalized_id(raw_value: str) -> str:
    """Убирает простые кавычки и комментарий из значения id."""
    value = raw_value.split(" #", 1)[0].strip()
    return value.strip("\"'")


def check_ids(
    texts: dict[Path, str], errors: list[str]
) -> None:
    occurrences: dict[str, list[str]] = defaultdict(list)

    for path, text in texts.items():
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = ID_LINE_RE.match(line)
            if not match:
                continue
            value = normalized_id(match.group(1))
            location = f"{display(path)}:{line_number}"
            if not value:
                errors.append(f"{location}: пустое значение id")
                continue
            if not ID_RE.fullmatch(value):
                errors.append(
                    f"{location}: id '{value}' должен состоять из строчных букв, "
                    "цифр и сегментов, разделённых точками или дефисами, без пробелов"
                )
            occurrences[value].append(location)

    for value, locations in sorted(occurrences.items()):
        if len(locations) > 1:
            errors.append(
                f"повторяющийся id '{value}': {', '.join(locations)}"
            )


def link_target(raw_target: str) -> str:
    """Извлекает путь, отбрасывая title и якорь Markdown-ссылки."""
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    else:
        # В этом шаблоне локальные пути не содержат пробелов. Остаток — title.
        target = target.split(maxsplit=1)[0]
    return unquote(target.split("#", 1)[0])


def check_markdown_links(
    texts: dict[Path, str], errors: list[str]
) -> None:
    for path, text in texts.items():
        if path.suffix.lower() != ".md":
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                target = link_target(match.group(1))
                if (
                    not target
                    or target.startswith(("http://", "https://", "mailto:", "data:"))
                ):
                    continue
                candidate = (
                    REPO_ROOT / target.lstrip("/")
                    if target.startswith("/")
                    else path.parent / target
                )
                if not candidate.resolve().exists():
                    errors.append(
                        f"{display(path)}:{line_number}: ссылка ведёт на "
                        f"отсутствующий путь '{target}'"
                    )


def section_bodies(text: str) -> dict[str, list[str]]:
    """Собирает содержимое разделов второго уровня до следующего заголовка."""
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            if level == 2:
                current = match.group(2).strip()
                bodies.setdefault(current, [])
            elif level <= 2:
                current = None
            continue
        if current is not None:
            bodies[current].append(line)
    return bodies


def has_meaningful_content(lines: list[str]) -> bool:
    """Считает TODO содержимым шаблона, но не пустые комментарии/разделители."""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") or stripped in {"---", "```"}:
            continue
        return True
    return False


def check_required_sections(
    texts: dict[Path, str], errors: list[str], warnings: list[str]
) -> None:
    for relative, section_names in REQUIRED_SECTIONS.items():
        path = REPO_ROOT / relative
        text = texts.get(path)
        if text is None:
            continue
        bodies = section_bodies(text)
        for name in section_names:
            if name not in bodies:
                errors.append(f"{relative}: отсутствует обязательный раздел '## {name}'")
            elif not has_meaningful_content(bodies[name]):
                warnings.append(f"{relative}: обязательный раздел '## {name}' пуст")


def check_h1(texts: dict[Path, str], warnings: list[str]) -> None:
    for path, text in texts.items():
        if path.suffix.lower() != ".md":
            continue
        if not any(re.match(r"^#\s+\S", line) for line in text.splitlines()):
            warnings.append(f"{display(path)}: нет заголовка первого уровня")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    check_required_files(errors)
    check_reset_template(errors)
    text_paths = repository_text_files()
    texts = load_texts(text_paths, errors)
    check_entity_front_matter(texts, errors)
    check_entity_checkpoint_ids(texts, errors)
    check_continuity(texts, errors)
    check_checkpoint_chain(texts, errors)
    check_module_campaign_binding(texts, errors)
    check_module_override_targets(texts, errors)
    check_ids(texts, errors)
    check_markdown_links(texts, errors)
    check_required_sections(texts, errors, warnings)
    check_legacy_journal_references(texts, errors)
    check_project_attachment_instructions(texts, errors)
    check_h1(texts, warnings)

    print("Проверка репозитория кампании")
    print(f"Проверено текстовых файлов: {len(texts)}")

    if errors:
        print("\nОшибки:")
        for item in errors:
            print(f"  [ERROR] {item}")
    if warnings:
        print("\nПредупреждения:")
        for item in warnings:
            print(f"  [WARN] {item}")
    if not errors and not warnings:
        print("\nOK: ошибок и предупреждений не найдено.")
    elif not errors:
        print("\nOK: ошибок нет; предупреждения не влияют на код завершения.")

    print(f"\nИтого: ошибок — {len(errors)}, предупреждений — {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
