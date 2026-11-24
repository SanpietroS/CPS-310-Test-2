# CPS-310-Test-2
# CPS310 Test 2 — Zombie Simulator

Sean Sanpietro

## Running the program

No extra packages are needed.

Run the game:

```bash
python zombie_midterm2.py
```

Run the demo:

```bash
python zombie_midterm2.py --demo
```

In Spyder, run the saved file first, then enter:

```python
run_pipeline_demo()
```

Spyder uses thread workers to avoid Windows process-startup problems. Terminal runs use process workers for CPU parallelism. The game saves its state in SQLite. Set `RESET_DATABASE` to `False` to continue a saved game.

## Game rules and ontology

The `ONTOLOGY` dictionary defines humans, zombies, the grid, game state, and birth proposals. Humans move randomly, and zombies move toward the nearest human. When they share a cell, the human becomes a zombie. Surviving humans near another human may reproduce. Zombies may die randomly, starting the round after conversion.

The checks enforce grid boundaries, integer coordinates, positive grid dimensions, nonnegative rounds, correct infection counts, and human population limits. A newborn must occupy a free cell.

The board uses `H`, `Z`, and `.`. Zombies sharing a cell share one `Z`. The total below the board counts every zombie.

## Development pipeline

1. Keep the earlier AI-generated Stage 3 code as a baseline.
2. Define the game concepts, relationships, and constraints in the ontology.
3. Give the AI the code and ontology and request a revision plan.
4. Review the plan against the rules before accepting changes.
5. Implement the checked birth handler and connect it to event processing.
6. Test both birth handlers with the same inputs, then run event checks and a full game.
7. For failures, give the AI the input, expected result, actual result, and broken rule. Correct the code and test again.
8. Accept the revision when its checks pass. Save the prompts, ontology, intermediate code, and results.

Planning and implementation took place in this AI chat. The demo automates testing and saves the results.

## Why the controls help

The ontology gives the AI and reviewer a shared description of valid behavior. Plan review makes assumptions visible. Input checks catch invalid worker output before it enters the population. Ordered birth merging prevents duplicate births in one cell and respects capacity.

Testing both versions against the same expectations makes their behavior comparable. The demo fails if the revised birth handler fails a check. Saved results make the comparison reviewable. The rules and validators must be updated together when game behavior changes. Passing these tests covers the tested cases, rather than proving every future change correct.

## Major prompts

The original Stage 3 request used the homework PDF and Stage 2 code as context:

> I believe that is part to for the zombie simulator whatever is needed to be added show me and do it

> Make it as simple as you can from what you added

The main Test 2 requests used the new PDF and existing code:

> Whatever new that needs to be added show me and where

> Just write the new code over again start to finish but tell me where in the code you added the new stuff

> Do everything for the zombie simulator that is being asked. Do everything just if its a different part tell me

> Make sure its simple

The working instructions applied within this chat were to define the ontology, plan the birth-handler revision, validate inputs before merging, preserve valid behavior, compare both versions, and correct failed checks. These describe stages within this chat and were not separate API calls.

## Demo results

| Cases                     | Earlier AI code        | Revised code |
| Seven valid cases         | 7 passed               | 7 passed |
| Eight invalid-input cases | 0 rejected as required | 8 rejected |
| Total                     | 7/15 passed            | 15/15 passed |

Valid cases cover empty populations, free births, occupied cells, duplicate proposals, order, and capacity. Invalid cases cover bad coordinates, invalid existing agents, an oversized population, and zero grid width. Event checks and a full game also passed.

For example, the earlier birth handler accepts `(-1, 0)` as a newborn position. The revised handler rejects it without changing the input lists. The invalid inputs were deliberately supplied to simulate faulty worker output or a future code change. The normal worker already clamps birth coordinates.

This compares the project's earlier AI-generated code with its revised version. It shows that the added checks catch these faults. It does not measure how often an AI would introduce them or compare independent model runs.

## Evidence and submission

The demo creates an `evidence` folder beside the script containing:

- `ontology.json` — the ontology used.
- `comparison.json` — inputs, expected and actual results, and pass/fail outcomes.
- `results.txt` — the comparison summary.

Also include `stage3_original.py`, `plan.txt`, and `development-note.txt`. These preserve the earlier code, revision plan, and a demo-runner failure and correction.

During development, a newline-quoting error was corrected. Windows startup problems later led to removing the subprocess launcher and using threads in interactive consoles. Terminal process workers and simulated interactive thread workers passed testing. The exact user Spyder session remains unverified.

Submit the Python file, this README, and the evidence folder through GitHub.

