"""Live evaluation product (M0): a user picks a registered demo website and states a goal; a bounded background job runs the EXISTING resumable investigation pipeline; the UI polls durable state.
M0 executes in MOCK mode only (rule-generated tasks, scripted browser agent, scripted investigator): no model call, no key, no spend. M1 swaps the execution mode inside `worker.py`; the job
contract, the API and the UI do not change."""
