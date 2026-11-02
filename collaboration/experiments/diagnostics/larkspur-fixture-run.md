# Diagnostics: larkspur (dev_fixture behaviour)

Versions: original `2f9fd2ce09a0`, modified `edb9a5d2884a`

Structural change in **modified**: resolved 3 ('course fee' is only on item pages, not on the /courses listing; 'seats left' is only on item pages, not on the /courses listing; 'duration' is only on item pages, not on the /courses listing), introduced 0.

## Hypothesis (6)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `H-d92df0a655` | hypothesis | medium | original | Listing cards omit 'campus': suspected contributor to item-page navigation on task(s) 3 | State campus on each card of /courses (visible text next to the item name). |
| `H-93873c763b` | hypothesis | medium | original | Listing cards omit 'class day': suspected contributor to item-page navigation on task(s) 6 | State class day on each card of /courses (visible text next to the item name). |
| `H-4d1bd64f93` | hypothesis | medium | original | Listing cards omit 'course fee': suspected contributor to item-page navigation on task(s) 1, 2, 7 | State course fee on each card of /courses (visible text next to the item name). |
| `H-f350d1b34c` | hypothesis | medium | original | Listing cards omit 'duration': suspected contributor to item-page navigation on task(s) 4 | State duration on each card of /courses (visible text next to the item name). |
| `H-f6094ac859` | unverified | info | original | Risk only: no evaluated task compares items by 'materials' | State materials on each card of /courses (visible text next to the item name). |
| `H-efdf6bb080` | unverified | info | original | Risk only: no evaluated task compares items by 'seats left' | State seats left on each card of /courses (visible text next to the item name). |

## Behavioral (2)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `B-1a0a4f1b6a` | observed | low | modified | unnecessary navigation on task 2 (1/1 trials) | Check the pages visited off the evidence path: navigation labels may be misleading the agent. |
| `B-657b3d9805` | observed | low | modified | unnecessary navigation on task 4 (1/1 trials) | Check the pages visited off the evidence path: navigation labels may be misleading the agent. |

## Structural (11)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `S-e260dd1253` | observed | medium | original | 'campus' is only on item pages, not on the /courses listing | State campus on each card of /courses (visible text next to the item name). |
| `S-29db5c51b3` | observed | medium | original | 'class day' is only on item pages, not on the /courses listing | State class day on each card of /courses (visible text next to the item name). |
| `S-0bc157f0a1` | observed | medium | original | 'course fee' is only on item pages, not on the /courses listing | State course fee on each card of /courses (visible text next to the item name). |
| `S-772df826eb` | observed | medium | original | 'duration' is only on item pages, not on the /courses listing | State duration on each card of /courses (visible text next to the item name). |
| `S-201f36d03d` | observed | medium | original | 'materials' is only on item pages, not on the /courses listing | State materials on each card of /courses (visible text next to the item name). |
| `S-74a8c5bd42` | observed | medium | original | 'seats left' is only on item pages, not on the /courses listing | State seats left on each card of /courses (visible text next to the item name). |
| `S-1bf982fc4f` | observed | info | original | none of 14 item pages carries structured data | Describe each item with schema.org JSON-LD (e.g. Product/Offer or Course) using the same values the page shows. |
| `S-e260dd1253` | observed | medium | modified | 'campus' is only on item pages, not on the /courses listing | State campus on each card of /courses (visible text next to the item name). |
| `S-29db5c51b3` | observed | medium | modified | 'class day' is only on item pages, not on the /courses listing | State class day on each card of /courses (visible text next to the item name). |
| `S-201f36d03d` | observed | medium | modified | 'materials' is only on item pages, not on the /courses listing | State materials on each card of /courses (visible text next to the item name). |
| `S-1bf982fc4f` | observed | info | modified | none of 14 item pages carries structured data | Describe each item with schema.org JSON-LD (e.g. Product/Offer or Course) using the same values the page shows. |
