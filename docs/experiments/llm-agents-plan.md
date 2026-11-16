# LLM agents: experiment design and budget

Planning document, prices checked 2026-11-15. This backend is proposed, not implemented
or benchmarked. No paid inference or model training has been performed for this plan.

## Recommendation

Keep Python, kind, six regional workers, Calico, Redpanda and the independent
analytics consumer. Introduce interchangeable rule-based, local LLM, and hosted LLM
speaker/listener policies. Benchmark Qwen3-0.6B through llama.cpp first; compare a
small sample with a hosted model before committing to a long run. A shared inference
server can serve many agents: agents are separate persistent states, not separate
copies of the model. CPU is the first baseline; benchmark Vulkan separately.

Machine: Ryzen AI 5 340, six cores/twelve threads, approximately 30 GiB RAM,
Radeon 840M integrated graphics, no NVIDIA GPU. A quantized 0.6B model is a plausible
fit alongside the cluster. Raw four-bit weights alone are roughly 0.3 GB; actual
resident memory includes quantization metadata, runtime and KV cache. Measure peak
RSS, available RAM, prompt processing and aggregate generation throughput under the
running cluster. Neither vLLM acceleration nor NPU acceleration is assumed.

## What an agent actually does

Each individual owns an ID, region, cohort/age, social ties, interaction history,
private lexical evidence, and optionally action-policy values. The LLM receives a
bounded view of that individual's state. Never share a chat session between agents.

1. The world samples a task and objects. Example: speaker privately needs the
   listener to give the water vessel from a set of visible objects.
2. Speaker call: receives the task, its own lexical evidence and recent experiences;
   outputs a short utterance such as `give nara`. The utterance may be invented or
   adapted within the experiment's declared rules.
3. Listener call: receives the utterance, visible choices and its own memories.
   It selects an object/action or requests clarification. It never receives the
   speaker's private task, dictionary, intended answer or internal rationale.
4. The world executes that choice and computes success from task equality. The
   language model does not grade its own answer.
5. Feedback becomes a private memory event. A declared grounding/repair treatment
   can reveal the intended object afterward. Additional LLM repair calls cost extra.
6. Bounded memory is updated deterministically from observations and feedback.
   Initially do not purchase separate LLM reflection or summarization calls.

Use randomized artificial labels and shuffled object IDs. Ordinary English task
instructions are a scaffold; pretrained language knowledge remains a confound.
Do not name regions France/Spain or prompt agents to become French/Spanish.
Geography changes access to interlocutors, not instructions to invent a dialect.
Run fixed regional sound biases as an explicit separate treatment, including a
no-imposed-bias condition. A tiny model that fails this game is not evidence that
human communities could not develop linguistic conventions.

## Distributed execution and isolation

The coordinator schedules allowed encounters and advances a round barrier. Regional
workers own agent contexts; cross-region traffic must follow the same permitted
edges as the baseline. They call a common inference gateway for their own requests.
Gateway options: local llama-server; OpenAI Responses; OpenRouter chat completions.
The gateway has no shared conversational memory or agent-visible analytics access.

NetworkPolicy permits inference and ledger infrastructure during geographic
isolation while blocking region-to-region communication. The gateway must never
retrieve foreign memories or mix agents into one prompt. Keep the base model frozen
across regions; global online training would leak information across closed borders.
Separate region adapters would need distinct update streams and checkpoint histories.

Add durable inference records: logical call ID, attempt ID, agent/region/round,
model and provider/version, prompt template version, exact request/response,
parameters, token usage, latency, cost reservation and settlement, errors, and
memory transition. Persist each result before applying its state transition.
Replay stored responses after restart; temperature zero does not establish exact
reproducibility across server versions. A provider timeout can still charge for an
unknown result. Quarantine uncertain attempts against the budget, limit retries,
and never claim global exactly-once API billing.

Retain the existing round outbox and Redpanda transaction flow; independent analytics
deduplicates logical events. The gateway needs a durable atomic budget reservation
before dispatch, including concurrent calls and maximum output charges. Hard-stop
at the local run cap, checkpoint and report incomplete rounds honestly. Provider
budget alerts alone are insufficient. API credentials belong in local environment
or Kubernetes Secrets excluded from Git and event payloads.

## Cost model

Baseline: 360 people × 4 encounters × 2,000 rounds = 2,880,000 encounters.
At two calls per encounter this is 5,760,000 calls, before repair/evaluation.

Illustrative assumptions: average 400 input tokens and 40 BILLABLE output tokens
per call. Input includes instructions, schema and bounded private memory. Output
includes hidden reasoning if the model uses it. These are estimates, not measured
prompt sizes. No caching/batch discounts are assumed.

Cost = calls × (input_tokens × input_price_per_million +
                output_tokens × output_price_per_million) / 1,000,000.

| Backend | Input $/M | Output $/M | Full 360-person baseline | 24 people, 1 encounter/round, 2,000 rounds | 12 people, 1 encounter/round, 2,000 rounds |
| --- | ---: | ---: | ---: | ---: | ---: |
| OpenRouter Llama 3.2 3B Instruct | 0.0509 | 0.335 | $194.46 | $3.24 | $1.62 |
| OpenAI GPT-5 nano, deprecated; conditional availability | 0.05 | 0.40 | $207.36 | $3.46 | $1.73 |
| OpenAI GPT-5.6 Luna, reasoning none | 0.20 | 1.20 | $737.28 | $12.29 | $6.14 |
| Local Qwen3-0.6B | no token fee | no token fee | electricity + machine time | electricity + machine time | electricity + machine time |

Allow at least 25% extra for repairs, evaluation and retries: full-scale Llama about
$243 and Luna about $922 before platform fees/taxes. This contingency cannot absorb
unbounded memory or reasoning. Doubling average prompt size doubles the input part,
not the output part. OpenRouter's catalog listed the precise Llama rates above;
provider selection can change them. Pin provider, reject price increases, and
account for Standard's 5.5% credit-purchase fee. Free endpoints are unsuitable as the
assumed capacity for a reproducible multi-day run.

OpenAI currently marks GPT-4.1 nano shut down and GPT-5 nano/GPT-5.4 nano deprecated.
Do not depend on them for a new long-term system. Luna supports reasoning `none`;
set it explicitly because its documented default is medium. Account-specific access
must be checked before choosing it. GPT-5 nano is a conditional cheap comparison,
not a promise that this account can use it or that reasoning stays within 40 tokens.

## A $12 OpenAI-credit allocation

- Up to $1: calibration and failure tests; measure real tokens and task performance.
- Up to $8: a 12-agent, six-region, 2,000-round run (2 agents initially per region,
  1 encounter each per round, 48,000 calls). Luna base estimate $6.144; with 25%
  overhead $7.68. Stop at $8 even if not finished.
- Up to $1: held-out tests and a short control run, bounded by measured costs.
- Keep $2 unallocated. Aggregate spend limit for the project stage is $10.

This is a feasibility demonstration with very small communities, not an equivalent
replication of the 360-person run. Turnover/migration can empty small regions; freeze
both for the initial demonstration, then introduce them as treatments with declared
minimum-population rules. Do not silently transplant baseline demographic rates.
If measured prompts exceed the estimate, reduce encounters or use local inference;
do not spend the reserve automatically. A 24-agent 2,000-round Luna run already
exceeds $12 before overhead at these assumptions.

For OpenRouter, a 24-agent run starts around $3.24; an inference cap of $5 leaves
room for overhead if calibration confirms the assumptions. These funds are separate
from existing OpenAI credits. For stronger evidence, prefer several matched seeds
and controls locally over spending the entire budget on one larger demonstration.

## Time, local serving and experiment stages

At an illustrative aggregate generation speed of 50 output tokens/second, full
baseline output alone (230.4 million tokens) takes 53.3 days. At 20 tokens/second it
takes 133.3 days. A 24-agent run emits 3.84 million output tokens: 21.3 hours at 50/s
or 53.3 hours at 20/s, plus prompt processing and orchestration. These are arithmetic
scenarios, not benchmarks. Short answers, batching separate contexts and prefix
caching can help; actual aggregate throughput determines the schedule. At hosted
100 calls/minute, full baseline alone is 40 days; at 1,000/minute it is 4 days,
before sequential dependencies, rate limits, and overhead.

1. Implement backend contract, deterministic fake backend, durable call journal and
   budget gateway. Test restart, timeout charging reservations, isolation, malformed
   outputs, hidden-intention exclusion and concurrent budget enforcement.
2. Local benchmark: 200-500 encounters on Qwen3-0.6B, thinking disabled, bounded
   contexts. Predeclare schema-validity and task-learning checks. Suggested threshold:
   at least 99% valid actions, and learned-label comprehension above a shuffled-label
   control. Compare a capped hosted sample; do not reward only fluent prose.
3. Short pilots: six regions, 24 individuals, 100-300 rounds. Check memory retention,
   lexical reuse, communicative success and real cost. Tune mechanics here and freeze
   them before the confirmatory experiment; separate tuning seeds from test seeds.
4. Long feasibility run: keep 1-200 contact, 201-1500 isolation, 1501-2000 selective
   reconnection. Run the affordable population for the chosen backend. Save phase
   boundaries, transcripts and checkpointed memories. No wall-clock sleep is needed;
   a round is a simulation unit, not a historical year.
5. Research replication: matched connected-throughout, fractured/reconnected and
   no-learning controls across multiple seeds (initial target five per condition).
   Match agent counts and contact opportunities across backends. Treat runs as
   experimental units; report uncertainty between seeds, not millions of encounters
   as independent samples. Hosted cost multiplies by seeds × conditions.

Measures: task success, repair rate, lexical diversity, variant persistence,
within/between-region differences, direction-specific held-out comprehension,
network exposure, memory/cohort effects, cost and latency. During isolation,
cross-region evaluation must run on read-only cloned contexts and return no feedback
to the main agents. Exact word distributions from the original model need a declared
mapping for free-form phrases; do not silently equate string distance with language.

## Reinforcement learning

Start with a contextual bandit over communication strategies: conventional form,
innovation, accommodation, or clarification. The world supplies an objective reward,
for example success minus small length and repair costs. Maintain per-agent action
values and update Q(a) <- Q(a) + alpha * (reward - Q(a)); context can include partner
familiarity or observed comprehension, without giving away hidden intentions.
Log action probabilities and exploration so choices remain auditable. Compare fixed
policy, memory-only adaptation and reward-updated policy with matched seeds.
This learns the communication policy, not the LLM's neural weights. Avoid rewarding
novelty or dialect difference in the primary treatment: that would bake in the
claimed emergence. Sweep cost penalties as explicit treatments.

Actual language-model RL is a later project: collect grounded trajectories, define
held-out rewards and anti-cheating checks, then benchmark small-model adapter
training. Inference feasibility does not establish training feasibility on this
integrated GPU. Training memory, rollout generation, optimizer state and wall time
require separate measurements; a cloud GPU would need a separate quoted budget.
Keep regional adapters independent through isolation. Do not promise PPO/GRPO or
hosted weight training for the $12 inference budget.

## Primary sources

- OpenAI Luna model, pricing and reasoning controls: https://developers.openai.com/api/docs/models/gpt-5.6-luna
- OpenAI nano lifecycle/pricing: https://developers.openai.com/api/docs/models/gpt-5-nano
- OpenAI 4.1 nano lifecycle: https://developers.openai.com/api/docs/models/gpt-4.1-nano
- OpenAI initial API setup: https://developers.openai.com/api/docs/quickstart
- OpenRouter machine-readable price catalog: https://openrouter.ai/api/v1/models
- OpenRouter Llama availability/providers: https://openrouter.ai/meta-llama/llama-3.2-3b-instruct
- OpenRouter fees: https://openrouter.ai/pricing
- Qwen model and thinking controls: https://huggingface.co/Qwen/Qwen3-0.6B
- llama.cpp CPU/Vulkan serving: https://github.com/ggml-org/llama.cpp
