import itertools
from collections import defaultdict
import pandas as pd
import argparse
import os

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
class Config:
    def __init__(self):
        self.num_groups = 172

        # Trainers per module (Module 1..5)
        self.trainers_per_module = [7, 5, 7, 7, 7]

        # Rest days between any two training days for the same group
        self.rest_days = 1

        # Slots per day (e.g., 2 = morning + afternoon)
        self.slots_per_day = 2

        # Max trainings per day per group
        self.max_trainings_per_day_per_group = 1

        # Venue definitions
        self.practice_rooms_per_venue = [4, 2, 4, 1, 1, 2, 3, 2, 5, 2, 4, 6]
        self.theory_rooms_per_venue  = [2, 4, 2, 1, 1, 1, 2, 3, 5, 2, 2, 7]

        # Optional: manually assign groups to venues
        # Example: [10, 12, 15, 8, 14, 13, 11, 16, 9, 17, 20, 27]
        self.groups_per_venue = [10, 12, 15, 8, 14, 13, 11, 16, 9, 17, 20, 27]

        # Maximum allowed difference between the busiest and least busy trainer
        # for the same module (in total days worked). If the threashold is exceeded, a warning will be printed.
        self.max_workload_diff = 3

        self.output_path = "C:/Users/yourname/Desktop/schedule.xlsx"

# ------------------------------------------------------------
# Module and block definitions
# Each block is a list of (module, activity) – the order is fixed.
# The actual calendar days are computed as start_day + i * (rest_days+1)
# where i is the index in the list.
# ------------------------------------------------------------
BLOCKS = {
    'M1': [(1, 'T'), (1, 'T'), (1, 'T'), (1, 'P'), (1, 'P'), (1, 'P')],
    'M2': [(2, 'T'), (2, 'T'), (2, 'T'), (2, 'P'), (2, 'P'), (2, 'P')],
    'M3': [(3, 'T'), (3, 'T'), (3, 'P'), (3, 'P')],
    'M4': [(4, 'T'), (4, 'T'), (4, 'P')],
    'M5': [(5, 'T'), (5, 'T')]
}
BLOCK_NAMES = ['M1', 'M2', 'M3', 'M4', 'M5']

# ------------------------------------------------------------
# Scheduling state
# ------------------------------------------------------------
class ScheduleState:
    def __init__(self, cfg):
        self.cfg = cfg

        # Number of venues
        self.num_venues = len(cfg.practice_rooms_per_venue)
        if len(cfg.theory_rooms_per_venue) != self.num_venues:
            raise ValueError("practice_rooms_per_venue and theory_rooms_per_venue must have same length")

        # Assign groups to venues
        if cfg.groups_per_venue is not None:
            if sum(cfg.groups_per_venue) != cfg.num_groups:
                raise ValueError("sum(groups_per_venue) must equal num_groups")
            if len(cfg.groups_per_venue) != self.num_venues:
                raise ValueError("groups_per_venue length must equal number of venues")
            self.venue_for_group = []
            for v, count in enumerate(cfg.groups_per_venue):
                self.venue_for_group.extend([v] * count)
        else:
            base = cfg.num_groups // self.num_venues
            rem = cfg.num_groups % self.num_venues
            self.venue_for_group = []
            for v in range(self.num_venues):
                count = base + (1 if v < rem else 0)
                self.venue_for_group.extend([v] * count)

        # Trainer state: module -> day -> slot -> set of trainer local ids
        self.trainer_busy = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        self.trainer_total_days = {m: [0] * cfg.trainers_per_module[m - 1] for m in range(1, 6)}

        # Room state: venue -> day -> slot -> set of room indices (0‑based)
        self.practice_room_usage = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        self.theory_room_usage = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

        # Trainer venue consistency
        self.trainer_last_venue = {m: [-1] * cfg.trainers_per_module[m - 1] for m in range(1, 6)}
        self.trainer_venue_freq = {
            m: [defaultdict(int) for _ in range(cfg.trainers_per_module[m - 1])]
            for m in range(1, 6)
        }

        # Group constraints
        self.group_last_day = [-10**9] * cfg.num_groups
        self.group_busy_days = [set() for _ in range(cfg.num_groups)]

        self.assignments = []

    # ------------------------------------------------------------
    def can_assign_sessions(self, venue, day, sessions):
        """Check if the list of (module, activity) sessions can fit into slots on that day."""
        slots = self.cfg.slots_per_day
        used_trainers = defaultdict(lambda: defaultdict(int))
        used_theory = defaultdict(int)
        used_practice = defaultdict(int)

        for slot in range(slots):
            for mod in range(1, 6):
                used_trainers[slot][mod] = len(self.trainer_busy[mod][day][slot])
            used_theory[slot] = len(self.theory_room_usage[venue][day][slot])
            used_practice[slot] = len(self.practice_room_usage[venue][day][slot])

        for mod, act in sessions:
            assigned = False
            for slot in range(slots):
                if used_trainers[slot][mod] >= self.cfg.trainers_per_module[mod - 1]:
                    continue
                if act == 'T':
                    if used_theory[slot] >= self.cfg.theory_rooms_per_venue[venue]:
                        continue
                else:
                    if used_practice[slot] >= self.cfg.practice_rooms_per_venue[venue]:
                        continue
                used_trainers[slot][mod] += 1
                if act == 'T':
                    used_theory[slot] += 1
                else:
                    used_practice[slot] += 1
                assigned = True
                break
            if not assigned:
                return False
        return True

    # ------------------------------------------------------------
    def can_place_block(self, block_name, start_day, group_id):
        """
        Check if the block can be placed starting at start_day.
        The block's sessions are placed on days:
            start_day + i * (rest_days + 1)   for i in range(len(sessions))
        """
        rest = self.cfg.rest_days
        gap = rest + 1
        sessions = BLOCKS[block_name]  # list of (module, activity)
        venue = self.venue_for_group[group_id]

        temp_last = self.group_last_day[group_id]
        temp_busy = self.group_busy_days[group_id].copy()

        for i, (mod, act) in enumerate(sessions):
            day = start_day + i * gap
            # Check group constraints
            if day < temp_last + rest + 1:
                return False
            if len(temp_busy.intersection([day])) >= self.cfg.max_trainings_per_day_per_group:
                return False
            # Check trainer/room capacities for this day
            if not self.can_assign_sessions(venue, day, [(mod, act)]):
                return False
            # Update temporary state for next iteration
            temp_last = day
            temp_busy.add(day)

        return True

    # ------------------------------------------------------------
    def find_earliest_start(self, block_name, lower_bound, group_id):
        for start in range(lower_bound, lower_bound + 2000):
            if self.can_place_block(block_name, start, group_id):
                return start
        return None

    # ------------------------------------------------------------
    def assign_session(self, day, module, activity, group_id, preferred=None):
        venue = self.venue_for_group[group_id]
        slots = self.cfg.slots_per_day
        num_trainers = self.cfg.trainers_per_module[module - 1]

        for slot in range(slots):
            # Trainer selection
            trainer = None
            busy_this_slot = self.trainer_busy[module][day][slot]

            if preferred is not None and preferred not in busy_this_slot and preferred < num_trainers:
                trainer = preferred
            else:
                free = [t for t in range(num_trainers) if t not in busy_this_slot]
                if not free:
                    continue
                min_work = min(self.trainer_total_days[module][t] for t in free)
                candidates = [t for t in free if self.trainer_total_days[module][t] == min_work]
                if len(candidates) > 1:
                    same_last = [t for t in candidates if self.trainer_last_venue[module][t] == venue]
                    if same_last:
                        trainer = max(same_last, key=lambda t: self.trainer_venue_freq[module][t].get(venue, 0))
                    else:
                        trainer = max(candidates, key=lambda t: self.trainer_venue_freq[module][t].get(venue, 0))
                else:
                    trainer = candidates[0]

            if trainer is None:
                continue

            # Room selection
            if activity == 'P':
                used = self.practice_room_usage[venue][day][slot]
                capacity = self.cfg.practice_rooms_per_venue[venue]
            else:
                used = self.theory_room_usage[venue][day][slot]
                capacity = self.cfg.theory_rooms_per_venue[venue]

            room = None
            for r in range(capacity):
                if r not in used:
                    room = r
                    break

            if room is None:
                continue

            # Valid assignment
            self.trainer_busy[module][day][slot].add(trainer)
            self.trainer_total_days[module][trainer] += 1
            self.trainer_last_venue[module][trainer] = venue
            self.trainer_venue_freq[module][trainer][venue] += 1

            if activity == 'P':
                self.practice_room_usage[venue][day][slot].add(room)
            else:
                self.theory_room_usage[venue][day][slot].add(room)

            self.group_busy_days[group_id].add(day)
            self.group_last_day[group_id] = max(self.group_last_day[group_id], day)

            offset = sum(self.cfg.trainers_per_module[:module - 1])
            global_id = offset + trainer + 1

            self.assignments.append({
                'day': day,
                'slot': slot + 1,
                'group': group_id,
                'module': module,
                'activity': activity,
                'trainer': global_id,
                'venue': venue,
                'room': room + 1
            })

            return trainer

        raise RuntimeError(f"No free trainer/room for module {module} on day {day}")

    # ------------------------------------------------------------
    def schedule_group(self, group_id):
        best_perm = None
        best_finish = float('inf')
        best_starts = None

        gap = self.cfg.rest_days + 1

        for perm in itertools.permutations(BLOCK_NAMES):
            starts = []
            current_day = 0
            feasible = True
            for blk in perm:
                start = self.find_earliest_start(blk, current_day, group_id)
                if start is None:
                    feasible = False
                    break
                starts.append(start)
                # The block occupies days: start, start+gap, start+2*gap, ... up to last session
                last_session_index = len(BLOCKS[blk]) - 1
                last_day = start + last_session_index * gap
                current_day = last_day + 1  # next block can start after the last day of this block
            if feasible:
                finish = current_day - 1
                if finish < best_finish:
                    best_finish = finish
                    best_perm = perm
                    best_starts = starts

        if best_perm is None:
            raise RuntimeError(f"Could not schedule group {group_id}")

        # Assign trainers with continuity
        preferred = {}
        for blk, start_day in zip(best_perm, best_starts):
            for i, (mod, act) in enumerate(BLOCKS[blk]):
                day = start_day + i * gap
                assigned = self.assign_session(day, mod, act, group_id, preferred.get(mod))
                preferred[mod] = assigned

# ------------------------------------------------------------
# Export to Excel (unchanged)
# ------------------------------------------------------------
def export_to_excel(state, cfg, output_path):
    if not state.assignments:
        print("No assignments to export.")
        return

    slots = cfg.slots_per_day
    max_day = max(a['day'] for a in state.assignments)
    total_slots = (max_day + 1) * slots

    calendar = [[''] * total_slots for _ in range(cfg.num_groups)]
    for ass in state.assignments:
        day = ass['day']
        slot = ass['slot'] - 1
        flat_idx = day * slots + slot
        group = ass['group']
        cell = f"{ass['module']}-{ass['activity']}-{ass['trainer']}-{ass['venue']}-{ass['room']}"
        if calendar[group][flat_idx] == '':
            calendar[group][flat_idx] = cell
        else:
            calendar[group][flat_idx] += '\n' + cell

    detailed = pd.DataFrame(state.assignments)
    detailed.rename(columns={
        'day': 'Day',
        'slot': 'Slot',
        'group': 'Group',
        'module': 'Module',
        'activity': 'Activity',
        'trainer': 'Trainer',
        'venue': 'Venue',
        'room': 'Room'
    }, inplace=True)

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        detailed.to_excel(writer, sheet_name='Detailed', index=False)

        cal_df = pd.DataFrame(calendar)
        cal_df.index.name = 'Group'
        header = [f"Day {d+1}-{s+1}" for d in range(max_day + 1) for s in range(slots)]
        cal_df.columns = header
        cal_df.to_excel(writer, sheet_name='Calendar')

    print(f"Schedule exported to {output_path}")

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    cfg = Config()

    parser = argparse.ArgumentParser(description='Schedule training with rest between every training day.')
    parser.add_argument('--groups', type=int, default=cfg.num_groups, help='Number of groups')
    parser.add_argument('--rest', type=int, default=cfg.rest_days, help='Rest days between any two training days')
    parser.add_argument('--slots', type=int, default=cfg.slots_per_day, help='Slots per day')
    parser.add_argument('--max-per-day', type=int, default=cfg.max_trainings_per_day_per_group,
                        help='Max trainings per day per group')
    parser.add_argument('--trainers', type=int, nargs=5, metavar=('M1','M2','M3','M4','M5'),
                        help='Trainers per module')
    parser.add_argument('--practice-rooms', type=str, default=','.join(map(str, cfg.practice_rooms_per_venue)),
                        help='Practice rooms per venue')
    parser.add_argument('--theory-rooms', type=str, default=','.join(map(str, cfg.theory_rooms_per_venue)),
                        help='Theory rooms per venue')
    parser.add_argument('--groups-per-venue', type=str, default=None,
                        help='Comma‑separated list of groups per venue')
    parser.add_argument('--output', type=str, default=cfg.output_path, help='Output Excel path')
    parser.add_argument('--max-workload-diff', type=int, default=cfg.max_workload_diff,
                        help='Max allowed trainer workload difference per module (warning only)')
    args = parser.parse_args()

    cfg.num_groups = args.groups
    cfg.rest_days = args.rest
    cfg.slots_per_day = args.slots
    cfg.max_trainings_per_day_per_group = args.max_per_day
    cfg.max_workload_diff = args.max_workload_diff

    if args.trainers:
        cfg.trainers_per_module = list(args.trainers)

    if args.practice_rooms:
        cfg.practice_rooms_per_venue = [int(x.strip()) for x in args.practice_rooms.split(',') if x.strip()]
    if args.theory_rooms:
        cfg.theory_rooms_per_venue = [int(x.strip()) for x in args.theory_rooms.split(',') if x.strip()]

    if args.groups_per_venue:
        cfg.groups_per_venue = [int(x.strip()) for x in args.groups_per_venue.split(',') if x.strip()]
        if sum(cfg.groups_per_venue) != cfg.num_groups:
            raise ValueError("sum(groups_per_venue) must equal num_groups")
        if len(cfg.groups_per_venue) != len(cfg.practice_rooms_per_venue):
            raise ValueError("groups_per_venue length must match number of venues")

    cfg.output_path = args.output
    os.makedirs(os.path.dirname(os.path.abspath(cfg.output_path)), exist_ok=True)

    state = ScheduleState(cfg)

    print(f"Scheduling {cfg.num_groups} groups, rest={cfg.rest_days}, slots/day={cfg.slots_per_day}, max/day/group={cfg.max_trainings_per_day_per_group}")
    print(f"Venues: {len(cfg.practice_rooms_per_venue)}")
    print(f"Practice rooms per venue: {cfg.practice_rooms_per_venue}")
    print(f"Theory rooms per venue:  {cfg.theory_rooms_per_venue}")
    print(f"Trainers per module: {cfg.trainers_per_module}")

    for gid in range(cfg.num_groups):
        state.schedule_group(gid)
        if (gid + 1) % 20 == 0:
            print(f"  Scheduled {gid + 1} groups")

    # Check trainer balance
    for mod in range(1, 6):
        counts = state.trainer_total_days[mod]
        diff = max(counts) - min(counts)
        if diff > cfg.max_workload_diff:
            print(f"Warning: Module {mod} trainer workload diff = {diff} > {cfg.max_workload_diff}")
            print(f"  Counts: {counts}")
        else:
            print(f"Module {mod} balanced (diff {diff})")

    export_to_excel(state, cfg, cfg.output_path)

if __name__ == '__main__':
    main()