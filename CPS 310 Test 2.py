"""
CPS310 - Midterm 2
Zombie Simulator
Sean Sanpietro
"""

import argparse
import json
from pathlib import Path
import sys
from collections import Counter
import math
import os
import random
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


GROUP_MEMBERS = ["Sean Sanpietro"]

WIDTH = 25
HEIGHT = 10
MAX_HUMANS = WIDTH * HEIGHT

STARTING_HUMANS = 200
STARTING_ZOMBIES = 25
MAX_ROUNDS = 100

HUMAN_REPRODUCTION_CHANCE = 0.01
ZOMBIE_DEATH_CHANCE = 0.01

WORKERS = min(4, max(2, os.cpu_count() or 2))
ROUND_DELAY = 0.5
RESET_DATABASE = True

MINI_MAP_WIDTH = 25
MINI_MAP_HEIGHT = 10


ONTOLOGY = {
    "entities": ["Human", "Zombie", "Grid", "GameState", "BirthProposal"],
    "relationships": {
        "occupies": "Humans and zombies occupy grid cells.",
        "infects": "Zombies infect humans in the same cell.",
        "proposes": "Surviving humans near another human may propose births.",
        "accepts": "The merger accepts births into free cells.",
    },
    "rules": {
        "round": "Round numbers must be nonnegative numbers.",
        "position": "Positions must be numbers coordinates inside the grid.",
        "capacity": "Humans cannot exceed grid capacity.",
        "infection": "Each colliding human becomes one zombie.",
        "dimensions": "Grid dimensions must be positive numbers.",
    },
}


def make_executor():
    # Spyder and other interactive consoles use threads.
    if "IPython" in sys.modules or hasattr(sys, "ps1"):
        return ThreadPoolExecutor(max_workers=WORKERS)

    return ProcessPoolExecutor(max_workers=WORKERS)


def check_grid(width, height):
    if type(width) is not int or type(height) is not int:
        raise ValueError(ONTOLOGY["rules"]["dimensions"])

    if width <= 0 or height <= 0:
        raise ValueError(ONTOLOGY["rules"]["dimensions"])


def check_position(position, width, height):
    if not isinstance(position, (tuple, list)) or len(position) != 2:
        raise ValueError(ONTOLOGY["rules"]["position"])

    x, y = position

    if type(x) is not int or type(y) is not int:
        raise ValueError(ONTOLOGY["rules"]["position"])

    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(ONTOLOGY["rules"]["position"])


def resolve_births(survivors, zombies, proposed_births, width, height):
    check_grid(width, height)

    if len(survivors) > width * height:
        raise ValueError(ONTOLOGY["rules"]["capacity"])

    for position in survivors + zombies + proposed_births:
        check_position(position, width, height)

    result = list(survivors)
    occupied = {tuple(position) for position in survivors + zombies}

    for proposal in proposed_births:
        if len(result) >= width * height:
            break

        baby = tuple(proposal)

        if baby not in occupied:
            result.append(baby)
            occupied.add(baby)

    return result


def validate_state(state, width, height):
    check_grid(width, height)

    if type(state.round_number) is not int or state.round_number < 0:
        raise ValueError(ONTOLOGY["rules"]["round"])

    if len(state.humans) > width * height:
        raise ValueError(ONTOLOGY["rules"]["capacity"])

    for position in state.humans + state.zombies:
        check_position(position, width, height)


def validate_infections(humans, zombie_locations, survivors, infected):
    expected_survivors = []
    expected_infected = []

    for human in humans:
        if human in zombie_locations:
            expected_infected.append(human)
        else:
            expected_survivors.append(human)

    if (
        Counter(survivors) != Counter(expected_survivors)
        or Counter(infected) != Counter(expected_infected)
    ):
        raise ValueError(ONTOLOGY["rules"]["infection"])


class GameState:
    def __init__(self, round_number, humans, zombies):
        self.round_number = round_number
        self.humans = humans
        self.zombies = zombies


class MemoryStorage:
    def __init__(self):
        self.state = None

    def load(self):
        return self.state

    def save(self, state):
        self.state = state


class DatabaseStorage:
    def __init__(self, file_name):
        self.connection = sqlite3.connect(file_name)
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS runtime (round_number INTEGER);
            CREATE TABLE IF NOT EXISTS humans (x INTEGER, y INTEGER);
            CREATE TABLE IF NOT EXISTS zombies (x INTEGER, y INTEGER);
        """)

    def clear(self):
        self.connection.execute("DELETE FROM runtime")
        self.connection.execute("DELETE FROM humans")
        self.connection.execute("DELETE FROM zombies")
        self.connection.commit()

    def load(self):
        round_data = self.connection.execute(
            "SELECT round_number FROM runtime"
        ).fetchone()

        if round_data is None:
            return None

        humans = self.connection.execute(
            "SELECT x, y FROM humans"
        ).fetchall()

        zombies = self.connection.execute(
            "SELECT x, y FROM zombies"
        ).fetchall()

        return GameState(round_data[0], humans, zombies)

    def save(self, state):
        self.connection.execute("DELETE FROM runtime")
        self.connection.execute("DELETE FROM humans")
        self.connection.execute("DELETE FROM zombies")

        self.connection.execute(
            "INSERT INTO runtime VALUES (?)",
            (state.round_number,),
        )

        self.connection.executemany(
            "INSERT INTO humans VALUES (?, ?)",
            state.humans,
        )

        self.connection.executemany(
            "INSERT INTO zombies VALUES (?, ?)",
            state.zombies,
        )

        self.connection.commit()

    def close(self):
        self.connection.close()


def split_agents(agent_list):
    chunks = []
    chunk_size = max(1, math.ceil(len(agent_list) / WORKERS))

    for index in range(0, len(agent_list), chunk_size):
        chunks.append(agent_list[index:index + chunk_size])

    return chunks


def move_humans_worker(data):
    humans, seed = data
    generator = random.Random(seed)
    moved_humans = []

    for x, y in humans:
        direction = generator.randint(1, 4)

        if direction == 1:
            x += 1
        elif direction == 2:
            x -= 1
        elif direction == 3:
            y += 1
        else:
            y -= 1

        x = max(0, min(WIDTH - 1, x))
        y = max(0, min(HEIGHT - 1, y))

        moved_humans.append((x, y))

    return moved_humans


def find_neighbors_worker(data):
    zombies, humans = data
    moved_zombies = []

    for zombie in zombies:
        closest_human = humans[0]
        closest_distance = math.dist(zombie, closest_human)

        for human in humans:
            distance = math.dist(zombie, human)

            if distance < closest_distance:
                closest_distance = distance
                closest_human = human

        x, y = zombie

        if x < closest_human[0]:
            x += 1
        elif x > closest_human[0]:
            x -= 1

        if y < closest_human[1]:
            y += 1
        elif y > closest_human[1]:
            y -= 1

        moved_zombies.append((x, y))

    return moved_zombies


def process_events_worker(data):
    humans, zombie_locations, human_locations, seed, width, height = data

    generator = random.Random(seed)
    survivors = []
    infected = []
    babies = []

    for x, y in humans:
        if (x, y) in zombie_locations:
            infected.append((x, y))
            continue

        survivors.append((x, y))
        nearby_human = False

        for x_change in [-1, 0, 1]:
            for y_change in [-1, 0, 1]:
                if x_change == 0 and y_change == 0:
                    continue

                if (x + x_change, y + y_change) in human_locations:
                    nearby_human = True

        if nearby_human and generator.random() < HUMAN_REPRODUCTION_CHANCE:
            baby_x = x + generator.choice([-1, 0, 1])
            baby_y = y + generator.choice([-1, 0, 1])

            baby_x = max(0, min(width - 1, baby_x))
            baby_y = max(0, min(height - 1, baby_y))

            babies.append((baby_x, baby_y))

    return survivors, infected, babies


def zombie_death_worker(data):
    zombies, seed = data
    generator = random.Random(seed)
    remaining_zombies = []

    for zombie in zombies:
        if generator.random() > ZOMBIE_DEATH_CHANCE:
            remaining_zombies.append(zombie)

    return remaining_zombies


def process_events(humans, zombies, width, height, generator, executor=None):
    validate_state(GameState(0, humans, zombies), width, height)

    zombie_locations = set(zombies)
    human_locations = set(humans)
    jobs = []

    for chunk in split_agents(humans):
        seed = generator.randrange(2**64)

        jobs.append(
            (chunk, zombie_locations, human_locations, seed, width, height)
        )

    dispatch = map if executor is None else executor.map

    survivors = []
    infected = []
    proposed_births = []

    for living, new_zombies, babies in dispatch(process_events_worker, jobs):
        survivors.extend(living)
        infected.extend(new_zombies)
        proposed_births.extend(babies)

    validate_infections(
        humans, zombie_locations, survivors, infected
    )

    survivors = resolve_births(
        survivors, zombies, proposed_births, width, height
    )

    death_jobs = [
        (chunk, generator.randrange(2**64))
        for chunk in split_agents(zombies + infected)
    ]

    remaining_zombies = []

    for group in dispatch(zombie_death_worker, death_jobs):
        remaining_zombies.extend(group)

    validate_state(
        GameState(0, survivors, remaining_zombies),
        width,
        height,
    )

    return survivors, remaining_zombies


def check_events(executor):
    humans = [(0, 0), (0, 0), (3, 3)]
    zombies = [(0, 0)]
    expected = ([(3, 3)], [(0, 0)] * 3)

    for pool in (None, executor):
        result = process_events(
            humans, zombies, 4, 4, random.Random(1), pool
        )
        assert result == expected

        result = process_events(
            [], [], 4, 4, random.Random(1), pool
        )
        assert result == ([], [])

    # These seeds make both humans propose the same birth cell.
    class BirthSeeds:
        def __init__(self):
            self.seeds = iter((206, 849))

        def randrange(self, stop):
            return next(self.seeds)

    for pool in (None, executor):
        result = process_events(
            [(0, 0), (1, 0)], [], 3, 3, BirthSeeds(), pool
        )
        assert result == ([(0, 0), (1, 0), (0, 1)], [])


def demo_ontology():
    with make_executor() as executor:
        check_events(executor)

    for survivors, infected in (
        ([(0, 0)], []),
        ([], [(0, 0), (0, 0)]),
    ):
        try:
            validate_infections(
                [(0, 0)], {(0, 0)}, survivors, infected
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "An incorrect infection result was accepted"
            )

    print("PASS - Event and infection checks passed.")


# Earlier birth handling, preserved for the required comparison.
def baseline_births(survivors, zombies, proposed_births, width, height):
    survivors = list(survivors)
    zombie_locations = set(zombies)
    occupied = set(survivors) | zombie_locations

    for baby in proposed_births:
        if len(survivors) >= width * height:
            break

        if baby not in occupied:
            survivors.append(baby)
            occupied.add(baby)

    return survivors


def check_case(function, case):
    name, humans, zombies, proposals, width, height, expected = case

    original = (
        list(humans),
        list(zombies),
        list(proposals),
    )

    try:
        actual = function(
            humans, zombies, proposals, width, height
        )
    except ValueError:
        actual = "rejected"
    except Exception as error:
        actual = type(error).__name__

    unchanged = (humans, zombies, proposals) == original

    return {
        "case": name,
        "expected": expected,
        "actual": actual,
        "inputs_unchanged": unchanged,
        "passed": actual == expected and unchanged,
    }


def run_pipeline_demo():
    evidence = Path(__file__).resolve().parent / "evidence"
    evidence.mkdir(exist_ok=True)

    cases = [
        ("empty", [], [], [], 3, 3, []),
        (
            "free birth",
            [(0, 0)], [], [(1, 1)], 3, 3,
            [(0, 0), (1, 1)],
        ),
        (
            "human cell occupied",
            [(0, 0)], [], [(0, 0)], 3, 3,
            [(0, 0)],
        ),
        (
            "zombie cell occupied",
            [], [(1, 1)], [(1, 1)], 3, 3,
            [],
        ),
        (
            "duplicate proposals",
            [], [], [(1, 1), (1, 1)], 3, 3,
            [(1, 1)],
        ),
        (
            "capacity and order",
            [(0, 0)], [], [(1, 0), (0, 0)], 2, 1,
            [(0, 0), (1, 0)],
        ),
        (
            "full grid",
            [(0, 0)], [], [(0, 0)], 1, 1,
            [(0, 0)],
        ),

        # Deliberately invalid inputs for the comparison.
        (
            "negative coordinate",
            [], [], [(-1, 0)], 3, 3, "rejected",
        ),
        (
            "outside grid",
            [], [], [(3, 0)], 3, 3, "rejected",
        ),
        (
            "fractional coordinate",
            [], [], [(0.5, 0)], 3, 3, "rejected",
        ),
        (
            "malformed coordinate",
            [], [], [(1,)], 3, 3, "rejected",
        ),
        (
            "invalid survivor",
            [(-1, 0)], [], [], 3, 3, "rejected",
        ),
        (
            "invalid zombie",
            [], [(3, 0)], [], 3, 3, "rejected",
        ),
        (
            "oversized population",
            [(0, 0), (0, 0)], [], [], 1, 1, "rejected",
        ),
        (
            "zero width",
            [], [], [], 0, 3, "rejected",
        ),
    ]

    results = {}
    lines = ["Zombie Simulator - Test 2 demo", ""]

    for label, function in (
        ("Earlier AI baseline", baseline_births),
        ("Ontology-guided revision", resolve_births),
    ):
        rows = [check_case(function, case) for case in cases]
        results[label] = rows

        passed = sum(row["passed"] for row in rows)
        lines.append(
            f"{label}: {passed}/{len(rows)} checks passed"
        )

        for row in rows:
            status = "PASS" if row["passed"] else "FAIL"
            lines.append(
                f"  {status} - {row['case']}: {row['actual']}"
            )

        lines.append("")

    demo_ontology()

    storage = MemoryStorage()
    ZombieSimulation(storage).run(display=False)
    validate_state(storage.load(), WIDTH, HEIGHT)

    lines.append("Event checks and full game: PASS")

    approved = all(
        row["passed"]
        for row in results["Ontology-guided revision"]
    )

    lines.extend([
        "",
        f"Controlled revision gate: {'PASS' if approved else 'FAIL'}",
    ])

    (evidence / "comparison.json").write_text(
        json.dumps(results, indent=2) + "\n",
        encoding="utf-8",
    )

    (evidence / "results.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(lines))

    if not approved:
        raise SystemExit(1)


class ZombieSimulation:
    def __init__(self, storage):
        self.storage = storage

    def create_state(self):
        cells = []

        for x in range(WIDTH):
            for y in range(HEIGHT):
                cells.append((x, y))

        random.shuffle(cells)
        humans = cells[:STARTING_HUMANS]
        zombies = []

        for i in range(STARTING_ZOMBIES):
            x = random.randint(0, WIDTH - 1)
            y = random.randint(0, HEIGHT - 1)
            zombies.append((x, y))

        return GameState(0, humans, zombies)

    def run_parallel(self, executor, worker, jobs):
        all_agents = []

        for group in executor.map(worker, jobs):
            all_agents.extend(group)

        return all_agents

    def run(self, display=True):
        state = self.storage.load()

        if state is None:
            state = self.create_state()

        validate_state(state, WIDTH, HEIGHT)

        if not state.humans or not state.zombies:
            print("The saved game has already ended.")
            return

        with make_executor() as executor:
            while state.round_number < MAX_ROUNDS:
                state.round_number += 1
                round_start = time.perf_counter()

                human_jobs = []

                for chunk in split_agents(state.humans):
                    human_jobs.append(
                        (chunk, random.randint(1, 1000000))
                    )

                state.humans = self.run_parallel(
                    executor,
                    move_humans_worker,
                    human_jobs,
                )

                neighbor_start = time.perf_counter()
                neighbor_jobs = []

                for chunk in split_agents(state.zombies):
                    neighbor_jobs.append(
                        (chunk, state.humans)
                    )

                state.zombies = self.run_parallel(
                    executor,
                    find_neighbors_worker,
                    neighbor_jobs,
                )

                neighbor_time = (
                    time.perf_counter() - neighbor_start
                )

                event_start = time.perf_counter()

                state.humans, state.zombies = process_events(
                    state.humans,
                    state.zombies,
                    WIDTH,
                    HEIGHT,
                    random,
                    executor,
                )

                event_time = time.perf_counter() - event_start
                database_start = time.perf_counter()

                validate_state(state, WIDTH, HEIGHT)
                self.storage.save(state)

                database_time = (
                    time.perf_counter() - database_start
                )
                round_time = time.perf_counter() - round_start

                if display:
                    self.display_map(state)

                    print(
                        "Round: %.3fs | Neighbors: %.3fs | "
                        "Events: %.3fs | Storage: %.3fs"
                        % (
                            round_time,
                            neighbor_time,
                            event_time,
                            database_time,
                        )
                    )

                if len(state.humans) == 0:
                    print("All humans have been infected!")
                    print("The zombies win!")
                    return

                if len(state.zombies) == 0:
                    print("There are no zombies left!")
                    print("The humans survive!")
                    return

                if display:
                    time.sleep(ROUND_DELAY)

    def display_map(self, state):
        grid = []

        for y in range(MINI_MAP_HEIGHT):
            row = []

            for x in range(MINI_MAP_WIDTH):
                row.append(".")

            grid.append(row)

        for x, y in state.humans:
            map_x = x * MINI_MAP_WIDTH // WIDTH
            map_y = y * MINI_MAP_HEIGHT // HEIGHT
            grid[map_y][map_x] = "H"

        for x, y in state.zombies:
            map_x = x * MINI_MAP_WIDTH // WIDTH
            map_y = y * MINI_MAP_HEIGHT // HEIGHT
            grid[map_y][map_x] = "Z"

        print("\nROUND", state.round_number)

        for row in grid:
            print("".join(row))

        print("Humans:", len(state.humans), "/", MAX_HUMANS)
        print("Zombies:", len(state.zombies))


def main():
    print("Name:", ", ".join(GROUP_MEMBERS))
    print("Starting agents:", STARTING_HUMANS + STARTING_ZOMBIES)
    print("Workers:", WORKERS)

    storage = DatabaseStorage("CPS_310_Test_2.db")

    if RESET_DATABASE:
        storage.clear()

    game = ZombieSimulation(storage)
    game.run()
    storage.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zombie Simulator")
    parser.add_argument("--demo", action="store_true")

    interactive = "IPython" in sys.modules or hasattr(sys, "ps1")
    args = parser.parse_args([] if interactive else None)

    if args.demo:
        run_pipeline_demo()
    else:
        main()