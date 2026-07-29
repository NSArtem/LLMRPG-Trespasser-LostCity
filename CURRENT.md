---
checkpoint_id: cp-0002
active_scene_id: scene-0007
active_journal_id: journal.entry-0002
campaign_status: active
last_activity_at: 2026-07-29
---

# Актуальное состояние

Канонический снимок на checkpoint `cp-0002`. События после него считаются
рабочим состоянием текущего чата, пока не записан следующий checkpoint.

## Метаданные кампании

- **Название:** `Trespasser — The Lost City`
- **Система и редакция:** `Trespasser v2.1.3`
- **Приключение:** `TSR B4 — The Lost City (1982)`, адаптированное под Trespasser
- **Статус кампании:** `active`
- **Последнее обновление:** `cp-0002`

## Непрерывность

- **Checkpoint:** [`cp-0002`](checkpoints/cp-0002.yaml)
- **Активная сцена:** `scene-0007`
- **Активная запись журнала:** [`journal.entry-0002`](journal/entry-0002.md)
- **Последняя игровая активность:** `2026-07-29`
- **Статус:** можно продолжать в этом или новом чате

## Внутриигровая дата и время

Точная дата неизвестна. Первый день экспедиции в пирамиде; идёт **dungeon round 7**, потрачено 1 из 3 общих действий.

## Текущее местоположение

Группа находится внутри полностью обысканной [тайной комнаты №3](locations/pyramid-secret-room-3.md) (`location.pyramid.secret-room-3`). Каменная тайная дверь закрыта.

## Присутствующие персонажи

- [Нара](party/character-nara.md) (`character.nara`)
- [Севек](party/character-sevek.md) (`character.sevek`)
- [Орис](party/character-oris.md) (`character.oris`)
- [Тавра](party/character-tavra.md) (`character.tavra`)

## Непосредственная ситуация

В комнате лежат семь мёртвых стирджей. Четыре найденных драгоценных камня собраны вместе, но носитель и инвентарные слоты ещё не назначены. Пять пещерных саранчей не нашли тайную дверь и ушли по коридору на север.

## Активные угрозы

- Критическая жажда: таймер заполнен, настоящей воды нет; урон повторится в конце dungeon round 7.
- Пять гигантских пещерных саранчей живы и находятся где-то севернее тайной двери.
- Четыре гоблина получили дополнительную фору; их местоположение неизвестно.
- Четыре гигантские пчелы остаются живы в сокровищнице.
- Горящий грубый факел остаётся расходуемым источником света.

## Активные часы

- `clock.thirst` — **6/6**, последствия уже действуют.
- `clock.alarm` — **0/10**.
- См. [campaign/clocks.md](campaign/clocks.md).

## Важные ресурсы группы

- Один горящий грубый факел у Ориса; ещё два не зажжены.
- Девять светящихся желёз огненных жуков, вместе 1 слот; должны светиться около двух дней с момента извлечения.
- Пищи и воды нет; два бурдюка пусты.
- Набор «молоток и железные штыри» истощён: штыри остались в двух дверях.
- В [газовой комнате](locations/pyramid-gas-chamber.md) оставлены два грубых кинжала и два грубых коротких лука.
- В [мастерской](locations/pyramid-workshop.md) остаются шесть фляг старого масла и кузнечные инструменты; они осмотрены, но не собраны.
- Четыре драгоценных камня стоимостью 100 gp, 100 gp, 500 gp и 1000 gp по B4; носитель, слоты и Trespasser Value не назначены.

## Текущие состояния персонажей

- **Нара:** 22/28 HP; Endurance 12; Recovery Dice 12d6; критическая жажда.
- **Севек:** 12/15 HP; Endurance 11; Recovery Dice 11d6; критическая жажда.
- **Орис:** 11/17 HP; Endurance 11/12; Recovery Dice 12d6; критическая жажда; несёт факел.
- **Тавра:** 16/22 HP; Endurance 10/11; Recovery Dice 11d6; критическая жажда.
- **Resolve:** 0 у всех. Травм и иных продолжающихся состояний, кроме критической жажды, нет.

## Ожидающие решения

- Как использовать оставшиеся 2 общих действия dungeon round 7.
- Кто понесёт четыре драгоценных камня и сколько слотов они займут.
- Подтвердить схему перевода сокровищ B/X в Treasure Value Trespasser.
- Искать ли воду или место для отдыха до следующего тика жажды.
- Продолжать ли исследование северного коридора либо возвращаться в мастерскую.
- Исследовать ли узкое отверстие в северной стене комнаты.
- До следующего использования незаписанных способностей окончательно выбрать и зафиксировать все deeds/talents персонажей первого уровня.

## Недавно установленные факты

- `fact.workshop-three-door-layout`
- `fact.northwest-corridor-secret-door`
- `fact.room3-secret-door-mechanism`
- `fact.room3-stirges-slain`
- `fact.cave-locusts-passed-north`
- `fact.room3-four-gems`
- `fact.room3-north-aperture`
- `fact.room3-search-complete`
- См. [campaign/established-facts.md](campaign/established-facts.md).

## Файлы последнего checkpoint

- `CURRENT.md`
- `checkpoints/cp-0002.yaml`
- `journal/entry-0002.md`
- `party/party.md` и четыре файла персонажей
- `campaign/clocks.md`, `campaign/open-threads.md`, `campaign/established-facts.md`, `campaign/timeline.md`
- `locations/pyramid-workshop.md`, `locations/pyramid-bee-treasury.md`
- `locations/pyramid-northwest-corridor.md`, `locations/pyramid-secret-room-3.md`
- `npcs/goblin-survivors.md`, `npcs/stirges-room-3.md`, `npcs/giant-cave-locusts.md`
- `gm/module-overrides.md`
- `rules/rulings.md`

## Следующая рекомендуемая точка загрузки

Начать внутри `location.pyramid.secret-room-3`: тайная дверь закрыта, комната обыскана, dungeon round 7 имеет два оставшихся действия.
