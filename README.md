# Training Scheduler
A Python tool that schedules – potentially – complex training for any number of groups of trainees across multiple geographic venues, respecting rooms, trainers, rest days, and trainer travel constraints.

It was born from a real need: coordinating training for hundreds of groups across several venues, each venue with its own practice and theory rooms, and each trainer being an expert in only one module.

# Table of contents
1. [Vibe coding warning](#vibe-coding-warning)
2. [What this tool does](#what-this-tool-does)
3. [Quick start](#quick-start)
4. [Understanding the output](#understanding-the-output)
5. [How the scheduler works](#how-the-scheduler-works)
6. [Customising the scheduler — the `Config` class](#customising-the-scheduler--the-config-class)
7. [Using the script without theory / practice distinction](#using-the-script-without-theory--practice-distinction)
8. [Running from the command line](#running-from-the-command-line)
9. [Technical section (for developers)](#technical-section-for-developers)
    - [More detailed algorithm explanation](#more-detailed-algorithm-explanation)
    - [Data structures](#data-structures)
    - [Known issues and limitations](#known-issues-and-limitations)
    - [Possible additional features](#possible-additional-features)

# Vibe coding warning
This code has been created mainly with AI (DeepSeek) because I'm not able to code. It has been tested manually, randomly checking some days by filtering the Excel table.

# What this tool does
Imagine you need to organise the same training programme for many groups of people. The programme may be composed of modules, each module may have a certain number of theory sessions and practice sessions. Every group must go through all the modules, in some order, and may need to respect a rest period between two consecutive training days (because they need to digest what they learned or because they may have other commitments).

The groups are spread across different geographic areas (venues). Each venue contains a fixed number of rooms, some may be dedicated to theory and some to practice. Because of geographical constraints, every group is bound to one venue: its participants can only train in the rooms of the venue they belong to.

Trainers are not shared between modules: the trainers of Module 1 only teach Module 1, the trainers of Module 2 only Module 2, and so on. Trainers are also a scarce resource — each module has only a fixed number of them, and each trainer can deliver at most a fixed number of sessions per day (slots per day).

The scheduler produces an Excel calendar telling you, for every group and every day, which module, which activity, which trainer, which venue and which room are involved.

It also produces a detailed table with the same information in separate columns, easier to filter and analyse as a table

# Quick start
1. Install Python 3.10 or newer.
2. Install the required libraries:
```
pip install pandas openpyxl
```
3. Open the file in any text editor, scroll to the `Config` class, adjust the parameters (see below).
4. Run:
```
python "training-scheduler.py"
```
5. Find the Excel file at the path indicated in the `Config` class.

# Understanding the output
The Excel file has two sheets.

## Calendar
A grid where rows are groups and columns are days. Days are split into slots, so a column labelled `Day 3-2` means "day 3, slot 2".

In each cell you'll find a string in this format:
```
module-activity-trainer-venue-room
```
For example, `2-T-13-4-1` means: Module 2, Theory, trainer number 13, venue 4, room 1.

If a group has more than one training on the same day (possible only if you allow more than 1 training per day per group), they will appear on separate lines in the same cell.

## Detailed
A flat table with one row per session and these columns: `Day`, `Slot`, `Group`, `Module`, `Activity`, `Trainer`, `Venue`, `Room`.

This is the sheet you want to use if you need to filter, sort, or merge with other data.

## How the scheduler works

**Step 1 — Groups are attached to venues.** Each group belongs to exactly one venue, because participants can only train in the rooms of their own area. Either the script distributes groups evenly across venues, or you tell it exactly how many groups belong to each.

**Step 2 — For each group, the script tries every possible order of the modules.** For example, in the current configuration, there are 5 modules, so there are 5 × 4 × 3 × 2 × 1 = 120 possible orders. For each order, the script attempts to fit the modules as early as possible in the calendar. When it has tested all 120 orders, it keeps the one that finishes soonest. Then it moves on to the next group.

**Step 3 — Fitting a module into the calendar.** For a given module in a given order, the script looks for the earliest day the group can start it. To accept a day, it checks three things:

- **Trainer availability**: is there a free trainer for that module, in any slot of that day?
- **Room availability**: is there a free room of the right kind (theory or practice) in the group's venue, in the same slot?
- **Group rules**: does the group respect its own constraints? (Enough rest days since the previous session? Already busy that day?)

If all three checks pass, the session is placed. If any fails, the script tries the next day, and so on, until it finds a suitable one. This is why a session may end up a few days later than strictly necessary if the trainers or rooms are already busy.

**Step 4 — Assigning trainers.** Once all the calendar days are fixed, the script picks a trainer for every session. It follows this priority order:

1. **Continuity.** If the group already had a session of the same module with a certain trainer, the script tries to keep that same trainer. This gives the group consistency of teaching throughout a module.
2. **Workload balance.** Among the free trainers of that module, the script prefers the ones who have worked less, so the burden is shared fairly.
3. **Venue consistency.** Among those, the script prefers trainers who are already in the group's venue (or who have worked there often), so they travel less.
4. **Smallest ID.** If there are still ties, the trainer with the smallest number is chosen, for reproducibility.

**A note on continuity.** The continuity preference is **best‑effort**: it only works if the same trainer happens to be free on the days the group needs. If not, a different trainer is assigned and the preference is dropped. The script does **not** delay a session just to keep the same trainer, because that would lengthen the calendar. Continuity is nice to have, not a hard rule.

**A note on optimality.** The script is **locally optimal**, not **globally optimal**. It chooses the best option for each group *one at a time*, wihtout never coming back to previous allocations, but the final result may not be the absolute mathematical best. Think of it as packing a suitcase: you take items one by one and place them where they fit best at that moment, without ever rearranging everything to find the perfect packing. In our case, "packing one item" = "scheduling one group". For example, when the code schedules group 5, it picks the choice that looks best for group 5 at that moment. But that choice might make things harder for group 200 later on.

To produce the mathematically best calendar, the script would have to compare every possible combination of orderings, days, trainers and rooms for all groups simultaneously — an astronomically large number. Imagine a modest scenario: 10 venues, each serving 10 groups, 5 modules with 20 sessions. The total number of possible calendars would be on the order of 10²³⁰⁰. For comparison: the number of atoms in the observable universe is about 10⁸⁰. So the calendar you get is valid and reasonably compact, but it is not provably the theoretical minimum.

⚠️ Note: these calculations have been made by the AI.

# Customising the scheduler — the Config class
Everything you can tweak lives inside the `Config` class, right at the top of the script. Below is a description of every parameter.

## `num_groups`
How many groups you need to schedule. Example: `self.num_groups = 172`.

## `trainers_per_module`
A list of five numbers, one per module, telling how many trainers are available for each module. Example: `self.trainers_per_module = [7, 5, 7, 7, 7]` means 7 trainers for Module 1, 5 for Module 2, 7 for Module 3, and so on.

Trainers are not interchangeable: a trainer of Module 2 cannot teach Module 4. Each module's trainers are a separate pool.

## `rest_days`
Number of rest days between two consecutive training days for the same group. Example: `self.rest_days = 1` means that if a group trains on day 10, the next training day can be day 12 at the earliest.

Note: this applies between every pair of consecutive training days, including within a single module. If you want training days back‑to‑back, set this to 0.

## `slots_per_day`
How many training sessions a single trainer (or a single room) can host in one day. Example: `self.slots_per_day = 2` means morning + afternoon, `self.slots_per_day = 3` means morning + afternoon + evening.

## `max_trainings_per_day_per_group`
Maximum number of sessions that the same group can have in one day. Example: `self.max_trainings_per_day_per_group = 1` means 1 session per day. If you set 2 slots per day, it means that training can happen both in morning and afternoon, but a group participates to only one slot per day, leaving half of the day free for them.

## `practice_rooms_per_venue`
A list, one element per venue, telling how many practice rooms each venue has. Example: `self.practice_rooms_per_venue = [4, 2, 4, 1, 1, 2, 3, 2, 5, 2, 4, 6]`.

## `theory_rooms_per_venue`
Same as above but for theory rooms. Must have the same length as `practice_rooms_per_venue`.

## `groups_per_venue`
How many groups are attached to each venue. Two options:
- `self.groups_per_venue = None` — the code distributes groups as evenly as possible across venues.
- A list — for example `self.groups_per_venue = [10, 12, 15, 8, 14, 13, 11, 16, 9, 17, 20, 27]`. The sum must equal `num_groups`, and the length must equal the number of venues. This is what you want to use if you already know how many participants come from each area.

## `max_workload_diff`
A warning threshold. At the end of the run, the script checks whether, within each module, the busiest trainer worked significantly more days than the least busy one. If the difference exceeds this number, a warning is printed.

⚠️ This does not affect scheduling: the script will never refuse to schedule or delay a group to satisfy this threshold. It's just a signal that the group distribution across venues might be too unbalanced for the trainers to stay even. Raise it if you want fewer warnings, lower it if you want to be strict.

## `output_path`
Full path of the Excel file to produce. Example: `self.output_path = "C:/Users/yourname/Desktop/schedule.xlsx"`.

# Editing the `BLOCKS` dictionary
Below the Config class there is a section called `BLOCKS`. It describes, for each module, the ordered list of sessions it contains, in this format:
```
'M1': [(1, 'T'), (1, 'T'), (1, 'T'), (1, 'P'), (1, 'P'), (1, 'P')]
```
Each `(number, letter)` pair means "one session of module *number*, activity *letter*", where `T` = Theory and `P` = Practice. The list is ordered: the first element is the first session the group will take, the second element the second, and so on.

To change how many sessions a module has, or the sequence of theory/practice, just edit these lists.

# Using the script without theory / practice distinction
If your training program have no theory/practice split (it only has just "training sessions"), the script works still fine, without any modification to the code. Be sure to follow these two steps:

1. In the `BLOCKS` dictionary, only use `T`. The list now only contains `(module, 'T')` pairs.
2. In the Config, put all your rooms in `theory_rooms_per_venue`, and set `practice_rooms_per_venue` to a list of zeros of the same length. For example, if you have 12 venues with 6, 6, 6, 2, 2, 3, 5, 5, 10, 4, 6 and 13 rooms respectively:
```
self.practice_rooms_per_venue = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
self.theory_rooms_per_venue  = [6, 6, 6, 2, 2, 3, 5, 5, 10, 4, 6, 13]
```
Every session will be scheduled as "theory", using the theory room pool. The practice rooms are never requested, so their values don't matter — zeros are fine.

The output will still show `T` in the calendar and `T` in the Activity column. You can simply read `T` as "training" in your head.

# Running from the command line
⚠️ Note: this feature is actually not tested because I don't like to run from the command line

If you prefer, you can pass parameters on the command line without touching the file. Every Config parameter has a matching flag:
```
python "training-scheduler.py" \
    --groups 200 \
    --rest 5 \
    --slots 2 \
    --trainers 8 6 8 8 8 \
    --practice-rooms "4,2,4,1,1,2,3,2,5,2,4,6" \
    --theory-rooms "2,4,2,1,1,1,2,3,5,2,2,7" \
    --groups-per-venue "15,15,15,15,15,15,15,15,15,15,15,20" \
    --output "my_schedule.xlsx" \
    --max-workload-diff 5
```
Any flag you don't pass uses the corresponding value from `Config`.

⚠️ Note: the `BLOCKS` dictionary cannot currently be set from the command line — if you need to change the number or the order of sessions per module, edit the file directly.

# Technical section (for developers)
## More detailed algorithm explanation
The algorithm is a greedy, group‑by‑group scheduler with a local permutation search.

1. __Group assignment to venues__. Each group is assigned to exactly one venue. If `groups_per_venue` is `None`, distribution is round‑robin (equal as possible); otherwise the user‑provided list is used.
2. __Per‑group scheduling__. Groups are processed sequentially, from group 0 upwards. The order matters: earlier groups get "first pick" on the resource pool, later groups are fitted around them.
3. __Permutation search over block order__. For each group, the scheduler enumerates all `5! = 120` orderings of the five module blocks (according to the configuration you already find in the code, which is customizable). For each ordering, it tries to place each block as early as possible using a greedy earliest‑start search (`find_earliest_start`). The ordering that minimises the finish day of that group is chosen. Note that this is a local optimisation, not a global one.
4. __Feasibility check (`can_place_block`)__. Before a block is placed on a candidate start day, three things are verified for every session of the block:
   - Trainer availability in the specific module's pool, for that day and that slot.
   - Room availability in the group's venue, for that day and that slot.
   - Group constraints: rest days since the previous session, and maximum number of trainings per day.

The candidate start day is advanced by one calendar day until all three pass.

5. __Trainer assignment (`assign_session`)__, applied after the days are fixed, so it can never alter the makespan. The preference order is:

  - Continuity — the same trainer who already taught this module to this group.
  - Minimal workload — among free trainers of that module, those with the fewest days worked.
  - Venue consistency — among those, whoever was last assigned to the same venue, then whoever has worked most at that venue (reduces travel).
  - Smallest id — deterministic fallback.

6. __Slot and room selection__. For each session, slots are tried from `0` to `slots_per_day-1` (earliest first). For a given slot, the smallest available room is picked.

## Data structures
All state lives in `ScheduleState`:

- `venue_for_group: list[int]` — venue assigned to each group.
- `trainer_busy[module][day][slot]: set[int]` — local ids of busy trainers in each module, day and slot.
- `trainer_total_days[module]: list[int]` — cumulative days worked by each trainer of the module.
- `practice_room_usage[venue][day][slot]: set[int]` and `theory_room_usage[venue][day][slot]: set[int]` — occupied room indices.
- `trainer_last_venue[module][trainer]` and `trainer_venue_freq[module][trainer][venue]` — used by the venue consistency heuristic.
- `group_last_day[group]` and `group_busy_days[group]` — enforce group‑level constraints.
- `assignments: list[dict]` — the final schedule; one dict per session, with day, slot, group, module, activity, trainer, venue, room.

## Known issues and limitations
- Not globally optimal. The scheduler is greedy and processes groups in order. The final makespan can therefore be longer than the true optimum. In particular:
  - The permutation chosen for group *i* is the best for group *i* alone, given the current state. It may be a bad choice for group *i+1*, *i+2*, etc.
  - Groups with smaller ids get first pick on all resources. If `groups_per_venue` is set to a highly unbalanced distribution, later groups may be forced to start much later.
- No backtracking between groups. If a late group cannot be scheduled within a reasonable horizon (2000 days forward from its lower bound), `find_earliest_start` returns `None`, and the group is skipped — the script will then raise an error at the end when trying to assign trainers, because the block has no assigned start day. In practice this never happens with realistic inputs, but it's not handled gracefully.
- Fixed block sequence within a module. The `BLOCKS` dictionary determines the exact order of sessions inside a module. Once fixed, the scheduler cannot reorder them (for example, to move a theory session after a practice session to fit a specific gap).
- The 2000‑day search limit in `find_earliest_start` is hard‑coded. If you set up an extraordinarily sparse capacity scenario, the search could return `None` without a clear explanation.
- Excel columns are dense. With many groups and many days, the Calendar sheet can become extremely wide.
- I've never asked the AI ​​to refactor the code, because I honestly don't care, I wouldn't be able to fully understand it anyway. Moreover, the code is already fast.

## Possible additional features
⚠️ Note: Some of this features have been suggested by the AI.

These are features that would make the tool more powerful, for whoever would like to implement them in the original code.
- __Graphical user interface__. A simple desktop or web app where users can set Config parameters via forms, click "run", and preview the calendar without touching Python.
- __Rescheduling of one session__. Keeping all constraints, allow the user to drag a session to a different day and re‑validate the whole plan. Useful when an unexpected event disrupts the schedule.
- __Configurable activity types__. Currently only `T` and `P` exist. Let the user rename them, add more (e.g. `E` for exam, `W` for workshop, ecc.) and define per‑type room pools.
- __Improved optimisation__. Replace the greedy scheduler with:
  - A Constraint Programming (CP) or Integer Linear Programming (ILP) model using Google OR‑Tools or similar.
  - Or a local search / simulated annealing optimiser that starts from the current schedule and improves it.
- __Read input from Excel/CSV__. Let the user list groups, venues and rooms in a spreadsheet instead of editing Python lists.
- __Multi‑skill trainers__. Allow a trainer to teach more than one module, with optional efficiency penalties.
- __Trainer availability windows__. Mark some trainers as unavailable on specific dates (holidays, contract limits, etc.).
- __Export to `.ics` / Google Calendar__, so participants can subscribe to their own group's schedule.
- __Conflict detection report__. A post‑processing step that scans the Excel output and reports any violations (this would serve both as a sanity check and as a regression test).
- __Undo / redo of manual edits__. If a GUI is built, a versioned history of the schedule would be invaluable.
- __Parallel / distributed scheduling__. For very large instances, split groups across workers and merge.
- __Better logging__. Currently the script prints a progress line every 20 groups. A proper log file with timestamps and per‑group decisions would help debugging.
- __Unit tests__. A small test suite validating the invariants (no double‑booked trainer, no double‑booked room, rest days respected, etc.) would make contributions safer.
- __Packaging as a pip‑installable CLI__. Currently the user has to clone the repository and run a file. A pip install training-scheduler with a training-scheduler command would lower the barrier further.

## Contributing
Pull requests and issues are welcome. If you're proposing an algorithmic improvement, please include a short description of the scenario you are targeting.
