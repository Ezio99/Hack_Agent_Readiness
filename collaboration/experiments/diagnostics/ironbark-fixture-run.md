# Diagnostics: ironbark (dev_fixture behaviour)

Versions: original `d2824b210ed9`, modified `40c5d886963c`

Structural change in **modified**: resolved 3 ('delivery and collection' is only on item pages, not on the /hire listing; 'minimum hire' is only on item pages, not on the /hire listing; 'refundable deposit' is only on item pages, not on the /hire listing), introduced 0.

## Hypothesis (6)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `H-f05dd5fa72` | unverified | info | original | Risk only: no evaluated task compares items by 'fits' | State fits on each card of /accessories (visible text next to the item name). |
| `H-dc7701e844` | hypothesis | medium | original | Listing cards omit 'delivery and collection': suspected contributor to item-page navigation on task(s) 3 | State delivery and collection on each card of /hire (visible text next to the item name). |
| `H-a767de20f6` | hypothesis | medium | original | Listing cards omit 'minimum hire': suspected contributor to item-page navigation on task(s) 4 | State minimum hire on each card of /hire (visible text next to the item name). |
| `H-90bc5dd86b` | unverified | info | original | Risk only: no evaluated task compares items by 'per week' | State per week on each card of /hire (visible text next to the item name). |
| `H-3921bcc5bc` | unverified | info | original | Risk only: no evaluated task compares items by 'refundable deposit' | State refundable deposit on each card of /hire (visible text next to the item name). |
| `H-eb1bf8dece` | unverified | info | original | Risk only: no evaluated task compares items by 'weekend' | State weekend on each card of /hire (visible text next to the item name). |

## Behavioral (5)

| id | status | severity | version | finding | recommendation |
|---|---|---|---|---|---|
| `B-4b1ba13dbf` | observed | medium | original | unsupported answer on task 2 (1/1 trials) | Check whether the answer is reachable within the agent's view (e.g. below the fold of a long page) before trusting such passes. |
| `B-32eed2cc4e` | observed | medium | original | unsupported answer on task 5 (1/1 trials) | Check whether the answer is reachable within the agent's view (e.g. below the fold of a long page) before trusting such passes. |
| `B-b9a8e2797a` | observed | low | modified | unnecessary navigation on task 3 (1/1 trials) | Check the pages visited off the evidence path: navigation labels may be misleading the agent. |
| `B-373ec55891` | observed | medium | modified | unsupported answer on task 2 (1/1 trials) | Check whether the answer is reachable within the agent's view (e.g. below the fold of a long page) before trusting such passes. |
| `B-9a50440f22` | observed | medium | modified | unsupported answer on task 5 (1/1 trials) | Check whether the answer is reachable within the agent's view (e.g. below the fold of a long page) before trusting such passes. |

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
