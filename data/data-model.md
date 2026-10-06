# Slot Planner: Data Model

## Example input

```
works i have is
hiwi i have to work for 8 hrs a week, can compensate with sat and sunday also
thesis main focus need to work a fixed time every day
job applying either morning or evening like night every day 1hr
upskill theory
upskilling project coding daily some
keep saturday free monday to friday and sunday
night 1hr german A1
```

## Core idea

Plan and reality are stored separately.

- **Slots** are what I intended to do. The engine keeps reshaping future slots.
- **Activity logs** are what actually happened. They are never edited by the engine.

The engine's job in one sentence: compare logs against targets, then reshape the future slots.

All time is stored as **integer minutes**. "This week" is calculated (Monday to Sunday containing a date), never stored.

## Layers

| Table | Used by | Engine sees it? |
|---|---|---|
| messages | agents | No |
| plan_extraction | agents | No |
| activities | engine, agents | Yes |
| slots | engine, agents, UI | Yes |
| activity_logs | engine, agents | Yes |
| rules | engine | Yes |
| replan_proposals | agents, UI | Engine creates them |

The engine never knows an LLM exists.

## Tables

### 1. messages
Every user message, saved exactly as typed. Used for debugging and later as the eval dataset.

```
id
user_id
text              raw user text
intent            plan | log | replan | question   (set by the supervisor)
created_at
```

### 2. plan_extraction
The LLM's reading of a plan message, stored as-is for traceability. One extraction produces many activities.

```
id
user_id
message_id        the message it was built from
month             2026-10
llm_output        JSON, validated with Pydantic before anything else uses it
status            draft | active | archived    (only one active per month)
```

### 3. activities
The validated version of each activity. This is what the engine reads.

```
id
user_id
plan_extraction_id
name              "Thesis", "HiWi", "German A1"
target_type       daily | weekly
target_min        60 (daily) or 480 (weekly)
priority          1 = most important, gets freed time first
fixed_time        20:30 for German, null if flexible
preferred_window  morning | afternoon | night | any
allowed_days      [Mon, Tue, Wed, Thu, Fri, Sun]
max_min_per_day   360, null if no limit
locked            true if fixed_time is set. The engine never moves locked slots
```

`locked` comes from `fixed_time`, not from "repeats every day". Thesis repeats daily but must stay movable, because it receives freed time.

### 4. slots
A planned block of time. Many slots point to one activity.

```
id
user_id
activity_id       name is looked up through this, not copied
date
start
end
status            planned | done | skipped | replaced
source            plan | replan
```

### 5. activity_logs
What actually happened. One message can create several logs.

```
id
user_id
message_id        the message it came from
activity_id
date
minutes
slot_id           optional, if it matches a planned slot
```

### 6. rules
Global constraints for the user.

```
user_id
free_days         [Sat]
week_starts_on    Mon
day_window        08:00 to 22:00
slot_step_min     15
min_chunk_min     30    (smallest piece the engine may create when splitting)
```

### 7. replan_proposals
What the engine suggests. Nothing changes until I approve.

```
id
user_id
trigger_message_id
week_start
changes           list of (slot_id, from_activity_id, to_activity_id, start, end)
unresolved        list of (activity_id, minutes_short)
status            pending | approved | rejected
created_at
```

## LLM extraction format

The plan builder must return strict JSON. One fixed type per field, `null` for "not mentioned".

```json
{
  "intent": "plan",
  "activities": [
    {
      "name": "HiWi",
      "target_type": "weekly",
      "target_min": 480,
      "fixed_time": null,
      "preferred_window": "any",
      "allowed_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sun"],
      "max_min_per_day": null,
      "priority": null,
      "notes": "can make up hours on weekends"
    }
  ],
  "missing": [
    {"activity": "Upskill theory", "field": "target_min"},
    {"activity": "Project coding", "field": "target_min"}
  ]
}
```

## When the agent asks questions

Ask only when a field the engine needs is missing or unclear. Never ask about things it can fill in itself.

- Missing `target_min` (upskill theory, "daily some" for project): ask
- Missing `priority`: ask once for the whole list
- Two rules that conflict: ask
- Everything else: use defaults, mention them in the plan summary

## Replan flow

1. User sends a message ("did 5h HiWi, skipped thesis")
2. Agent saves the message, creates activity_logs, marks skipped slots
3. Engine calculates a replan_proposal
4. Agent explains it in plain language, asks only if something is unresolved
5. User approves or rejects
6. On approve, engine applies the changes to slots

## Worked example (first engine test)

Week of Oct 5. Monday logs: HiWi 300, Job apps 60, German 60. Thesis and project coding skipped.

| Activity | Weekly target | Done Mon | Planned Tue to Sun | Still needed | Difference |
|---|---|---|---|---|---|
| HiWi | 480 | 300 | 360 (Wed, Fri, Sun) | 180 | 180 surplus |
| Thesis | 1230 | 0 | 1020 (4 x 210 + Sun 180) | 1230 | 210 behind |
| Project coding | 300 | 0 | 240 (Tue to Fri) | 300 | 60 behind |

Freed: 180. Behind: 270. Thesis has higher priority, so all 180 goes to thesis.

Expected proposal:

| Slot | From | To |
|---|---|---|
| Sun 13:30 to 15:30 | HiWi | Thesis |
| Fri 14:00 to 15:00 | HiWi | Thesis |

Fri 15:00 to 16:00 stays HiWi. Unresolved: thesis 30 short, project 60 short.

## Design decisions

1. **Target reached early:** remaining slots of that activity are released to whatever is behind, by priority. If nothing is behind, they become free time.
2. **Release order:** release the latest slots in the week first. Sunday is the makeup day, so it goes first once it's not needed.
3. **Not enough freed time:** don't auto-carry to next week. Report it in `unresolved` and ask the user.
4. **Splitting:** allowed at slot_step boundaries, never smaller than min_chunk_min.
5. **Logs on free days:** count toward weekly totals. The engine just never plans on free days.
6. **Overshoot:** extra hours are a bonus. Next week's target doesn't change.
