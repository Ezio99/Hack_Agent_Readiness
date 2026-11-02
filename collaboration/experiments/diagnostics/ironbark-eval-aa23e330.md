# Diagnostics: ironbark (real_model behaviour)

Versions: original `d2824b210ed9`, modified `40c5d886963c`

Structural change in **modified**: resolved 3 ('delivery and collection' is only on item pages, not on the /hire listing; 'minimum hire' is only on item pages, not on the /hire listing; 'refundable deposit' is only on item pages, not on the /hire listing), introduced 0.

## Hypothesis (6)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `H-f05dd5fa72` | unverified | info | original | Risk only: no evaluated task compares items by 'fits' | State fits on each card of /accessories (visible text next to the item name). |
| `H-dc7701e844` | supported_exploratory | high | original | Listing cards omit 'delivery and collection': suspected contributor to item-page navigation on task(s) 3 | State delivery and collection on each card of /hire (visible text next to the item name). |
| `H-a767de20f6` | supported_exploratory | high | original | Listing cards omit 'minimum hire': suspected contributor to item-page navigation on task(s) 4 | State minimum hire on each card of /hire (visible text next to the item name). |
| `H-90bc5dd86b` | unverified | info | original | Risk only: no evaluated task compares items by 'per week' | State per week on each card of /hire (visible text next to the item name). |
| `H-3921bcc5bc` | supported_exploratory | high | original | Listing cards omit 'refundable deposit': suspected contributor to item-page navigation on task(s) 1, 2 | State refundable deposit on each card of /hire (visible text next to the item name). |
| `H-eb1bf8dece` | unverified | info | original | Risk only: no evaluated task compares items by 'weekend' | State weekend on each card of /hire (visible text next to the item name). |

## Behavioral (16)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `B-1cad0d65f6` | observed | high | original | budget exhaustion on task 1 (1/1 trials) | Find which pages consumed the budget (steps cited) and whether the needed facts could be reached in fewer steps. |
| `B-f10a66e7af` | observed | high | original | budget exhaustion on task 2 (1/1 trials) | Find which pages consumed the budget (steps cited) and whether the needed facts could be reached in fewer steps. |
| `B-b7e3dc8c6b` | observed | high | original | budget exhaustion on task 3 (1/1 trials) | Find which pages consumed the budget (steps cited) and whether the needed facts could be reached in fewer steps. |
| `B-58d76a395e` | observed | high | original | budget exhaustion on task 4 (1/1 trials) | Find which pages consumed the budget (steps cited) and whether the needed facts could be reached in fewer steps. |
| `B-4248cb4bce` | observed | medium | original | dead end on task 3 (1/1 trials) | Fix or remove the failing link or control (status and step cited). |
| `B-292d69f1be` | observed | high | original | incorrect answer on task 1 (1/1 trials) | Compare the agent's answer with the pages it saw (trial steps cited) to see where the needed information was missing or misread. |
| `B-b98cd888ca` | observed | high | original | incorrect answer on task 2 (1/1 trials) | Compare the agent's answer with the pages it saw (trial steps cited) to see where the needed information was missing or misread. |
| `B-60a86403f7` | observed | high | original | incorrect answer on task 3 (1/1 trials) | Compare the agent's answer with the pages it saw (trial steps cited) to see where the needed information was missing or misread. |
| `B-3cd0523564` | observed | high | original | incorrect answer on task 4 (1/1 trials) | Compare the agent's answer with the pages it saw (trial steps cited) to see where the needed information was missing or misread. |
| `B-baac85ec6c` | observed | medium | original | loop on task 1 (1/1 trials) | Inspect the two pages in the loop: the agent may be failing to find a link or fact it expects on one of them. |
| `B-7f529fa8aa` | observed | low | original | retry on task 1 (1/1 trials) | Inspect the repeated action: the target may not respond as the agent expects. |
| `B-abdc03bd08` | observed | low | original | revisit on task 1 (1/1 trials) | Check why the agent returned to this page: it may be a listing it must consult repeatedly to compare items. |
| `B-731c2075dd` | observed | low | original | revisit on task 2 (1/1 trials) | Check why the agent returned to this page: it may be a listing it must consult repeatedly to compare items. |
| `B-f0b3a4f5a7` | observed | low | original | revisit on task 3 (1/1 trials) | Check why the agent returned to this page: it may be a listing it must consult repeatedly to compare items. |
| `B-0a97c8eb9b` | observed | low | original | revisit on task 4 (1/1 trials) | Check why the agent returned to this page: it may be a listing it must consult repeatedly to compare items. |
| `B-80a6836707` | observed | high | modified | incorrect answer on task 1 (1/1 trials) | Compare the agent's answer with the pages it saw (trial steps cited) to see where the needed information was missing or misread. |

## Structural (11)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `S-f7ce0a5ad3` | observed | medium | original | 'fits' is only on item pages, not on the /accessories listing | State fits on each card of /accessories (visible text next to the item name). |
| `S-74da5c1c65` | observed | medium | original | 'delivery and collection' is only on item pages, not on the /hire listing | State delivery and collection on each card of /hire (visible text next to the item name). |
| `S-b042572203` | observed | medium | original | 'minimum hire' is only on item pages, not on the /hire listing | State minimum hire on each card of /hire (visible text next to the item name). |
| `S-0d2d172c57` | observed | medium | original | 'per week' is only on item pages, not on the /hire listing | State per week on each card of /hire (visible text next to the item name). |
| `S-fc900d5098` | observed | medium | original | 'refundable deposit' is only on item pages, not on the /hire listing | State refundable deposit on each card of /hire (visible text next to the item name). |
| `S-dcf2f6c941` | observed | medium | original | 'weekend' is only on item pages, not on the /hire listing | State weekend on each card of /hire (visible text next to the item name). |
| `S-50aa1180f0` | observed | info | original | none of 33 item pages carries structured data | Describe each item with schema.org JSON-LD (e.g. Product/Offer or Course) using the same values the page shows. |
| `S-f7ce0a5ad3` | observed | medium | modified | 'fits' is only on item pages, not on the /accessories listing | State fits on each card of /accessories (visible text next to the item name). |
| `S-0d2d172c57` | observed | medium | modified | 'per week' is only on item pages, not on the /hire listing | State per week on each card of /hire (visible text next to the item name). |
| `S-dcf2f6c941` | observed | medium | modified | 'weekend' is only on item pages, not on the /hire listing | State weekend on each card of /hire (visible text next to the item name). |
| `S-50aa1180f0` | observed | info | modified | none of 33 item pages carries structured data | Describe each item with schema.org JSON-LD (e.g. Product/Offer or Course) using the same values the page shows. |
