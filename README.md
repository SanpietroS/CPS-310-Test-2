# CPS 310 Test 2 — Zombie Simulator

Sean Sanpietro

## Run the demo

Keep `CPS_310_Test_2.py` and `CPS 310 Test 2 Results.py` in the same folder. Use Python 3. No extra packages are needed.

In Spyder, run `CPS 310 Test 2 Results.py`. In a terminal, run:

```text
python "CPS 310 Test 2 Results.py"
```

The demo saves the ontology and results in `evidence/`. Run `CPS_310_Test_2.py` to see the game board.

## Game rules

The ontology describes humans, zombies, the grid, game state, and births. Zombies infect humans in the same cell. Births need an empty cell. The code checks coordinates, grid size, round numbers, infection counts, and population limits.

## Development pipeline

1. Save the earlier AI-generated code for comparison.
2. Write the game rules in the ontology.
3. Give the AI the code and rules. Ask for a plan and review it.
4. Add checks for births, infections, and game state.
5. Test both versions with the same inputs. Run the event checks and a full game.
6. Fix failures, rerun the tests, and save the results.

## Results

The earlier version passed **7/15** checks. The revised version passed **15/15**. Both passed all seven valid cases. The revised code rejected all eight invalid inputs, including a birth at `(-1, 0)`. Checking proposals before adding them keeps invalid and duplicate births out of the game. The event checks and full game also passed.

## Major prompts

> I believe that is part to for the zombie simulator whatever is needed to be added show me and do it

> Make it as simple as you can from what you added

> Whatever new that needs to be added show me and where

> Just write the new code over again start to finish but tell me where in the code you added the new stuff

> Do everything for the zombie simulator that is being asked. Do everything just if its a different part tell me

> Make sure its simple

## Demo options

A simpler game is allowed if it still has enough behavior to test. Free-tier AI is allowed. No subscription is needed. Contact Fanchao right away if you hit AI limits or have no AI access. If you have no AI access, you can skip the demo with Fanchao’s permission.
