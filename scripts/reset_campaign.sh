#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
template_root="$repo_root/templates"
path_list="$template_root/reset-paths.txt"
assume_yes=false

if [[ "${1:-}" == "--yes" ]]; then
  assume_yes=true
elif [[ $# -ne 0 ]]; then
  printf 'Использование: %s [--yes]\n' "$0" >&2
  exit 2
fi

if [[ ! -f "$repo_root/MANIFEST.md" || ! -f "$repo_root/CURRENT.md" ]]; then
  printf 'Ошибка: не найден корень репозитория кампании: %s\n' "$repo_root" >&2
  exit 1
fi

if [[ ! -f "$path_list" ]]; then
  printf 'Ошибка: отсутствует список путей %s\n' "$path_list" >&2
  exit 1
fi

validate_path() {
  local relative_path="$1"
  case "$relative_path" in
    ""|/*|.|..|*/../*|../*|*/..)
      printf 'Ошибка: небезопасный путь в reset-paths.txt: %s\n' "$relative_path" >&2
      exit 1
      ;;
  esac
  if [[ ! -e "$template_root/$relative_path" ]]; then
    printf 'Ошибка: для %s нет шаблона\n' "$relative_path" >&2
    exit 1
  fi
}

while IFS= read -r relative_path || [[ -n "$relative_path" ]]; do
  [[ -z "$relative_path" || "$relative_path" == \#* ]] && continue
  validate_path "$relative_path"
done < "$path_list"

if [[ "$assume_yes" != true ]]; then
  printf '%s\n' \
    'Будут безвозвратно заменены текущие данные кампании:' \
    "$(sed 's/^/  - /' "$path_list")"
  read -r -p 'Введите RESET для продолжения: ' confirmation
  if [[ "$confirmation" != "RESET" ]]; then
    printf 'Сброс отменён.\n'
    exit 1
  fi
fi

while IFS= read -r relative_path || [[ -n "$relative_path" ]]; do
  [[ -z "$relative_path" || "$relative_path" == \#* ]] && continue
  rm -rf -- "$repo_root/$relative_path"
  cp -R -- "$template_root/$relative_path" "$repo_root/$relative_path"
done < "$path_list"

python3 "$repo_root/scripts/validate_repo.py"
printf 'Состояние до кампании восстановлено.\n'
