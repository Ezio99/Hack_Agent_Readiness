# Meta integration validation — 2026-10-27

Status: official protocol reviewed; offline adapter contract verified; authenticated
compatibility and live browser-agent trials **not verified**. No provider requests
or paid calls were made. Synthetic responses are test fixtures, not model output.

## Official requirements checked

- Base URL `https://api.meta.ai/v1`, bearer token read from the `MODEL_API_KEY` environment variable (or repository-root `.env`), and Muse Spark model IDs
  are documented in the [official overview](https://dev.meta.ai/docs/overview).
  The default candidate here is `muse-spark-1.3`. Access and billing require the
  participant's own account/key; availability has not been checked for this user.
- [Chat Completions](https://dev.meta.ai/docs/protocols/chat-completions) accepts
  a messages array at `/v1/chat/completions` and returns generated text through
  `choices[0].message.content`. We leave sampling at provider defaults, disable
  automatic retries, and set a per-response completion-token limit.
- [Image understanding](https://dev.meta.ai/docs/image-understanding) documents
  Chat Completions `image_url` content parts, including base64 data URLs. This
  matches Browser Use's screenshot serializer. The fixed profile enables DOM and
  high-detail screenshot observations.
- [Structured output](https://dev.meta.ai/docs/structured-output) documents
  `response_format.json_schema`. Its strict subset requires an object root,
  all object properties required, and `additionalProperties: false`; nested
  `anyOf` is allowed, `oneOf`/`allOf` are not. Tests inspect the actual optimized
  Browser Use action schema against these documented conditions.

## Adapter evidence

Browser Use 0.11.13's installed `ChatOpenAI` implementation was inspected. It
supports a custom base URL and sends messages, image parts and strict JSON schema
through its SDK. We explicitly omit its default temperature/frequency penalty
and remove legacy min-items fields from the schema. See the upstream
[provider reference](https://github.com/browser-use/browser-use/blob/main/skills/open-source/references/models.md).

Offline tests use HTTPX MockTransport to exercise the real serializer, SDK, image
payload, auth header, full agent action schema, response parsing and reported
usage. One SDK platform probe is prefilled in tests because this sandbox prevents
cross-thread event-loop notification. No remote transport is used in those tests.

This is evidence of matching request contracts, not proof the hosted service
accepts every generated schema or that the selected model solves browser tasks.
A later explicitly approved trial must validate authentication, model access,
schema acceptance, screenshots, browser actions and independent grading. All
attempts, including failures, must be retained. No fallback model is selected
silently. Model calls require the explicit CLI flag `--allow-model-calls`.

## Event rules

The [public event page](https://dev.meta.ai/events/global-hackathon) describes Meta
technology and the development window but did not establish detailed reuse rules
in the material inspected. Participant-specific rules remain unverified. All
executable code/tests/configuration in this implementation were written fresh;
no prototype assets or results were imported.

## PR #1 review safeguards

The reference profile is now `natural-shopping-v2`. One effective snapshot feeds
the model adapter and browser agent; model request timeout and completion-token
limit come from that snapshot. A per-run gate blocks calls beyond the configured
request-attempt cap before the provider adapter, including framework retries. SDK
retries remain disabled. Step/time/request limits do not guarantee a dollar cap.
No live or authenticated provider trial was performed for these changes. Raw
artifacts, especially screenshots and arbitrary model/page text, require privacy
inspection before publication. Next milestone remains separately approved Meta
authentication/compatibility validation followed by one controlled agent trial.
