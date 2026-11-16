# Completed baseline evidence

Run `42c2febb3e8c3cff12b2` completed 2,000 rounds and 2,880,000 conversations.
The independent ledger consumer verified all per-round counts and found zero
geographic boundary violations. These files are a compact copy of the completed
run report, configuration, audit, and figures; SHA-256 hashes identify this copy.

Full checkpoints, event outboxes, broker storage and analytics remain under
`runtime/` on this machine and are deliberately excluded from Git. This archive
is not a replacement for backing up that raw research data. The report contains
local runtime paths which are meaningful on the original machine only.

The source commit was created after the experiment, not before execution.
Worker image: `galapagos-regions:v2r2`, image ID
`sha256:ffee064bf39c2f67565d59f1748fdf27ecc171efdfbfc7b7b06ce382572b49c1`.
Analytics image: `galapagos-analytics:v1`, image ID
`sha256:6d4863cb0a06d7e2ecd038de9acfdadf40cee79580dc0dcf26af25a640030315`.

This is one stochastic seed, with imposed regional phonological biases. It does
not reconstruct historical Romance languages or establish a causal effect without
matched controls and replication. See `../../experiments/roman-fracture.md`.
