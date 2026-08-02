## todo

1. Parse the question into a structured query:

- intent (decision, commitment, preference, etc.)
- scope (contact, thread, event, task)
- time window (since yesterday, last week)
- freshness (active first, historical optional)

2. Fetch candidates with hard filters first:

- user_id, entity, status, expires_at, time range
- graph scope (direct entity, then one-hop linked entities)

3. Rank candidates (not just return all):

- intent match weight
- entity match weight
- recency decay
- importance weight
- optional semantic similarity on content

4. Return a compact context packet:

- top K facts only
- typed fields (no raw blobs)
- provenance (why selected)

5. Feed that packet to the model.

Why this is better

- Faster than free-form retrieval
- More accurate than pure semantic search
- Deterministic and explainable

If you want, I can define the exact scoring formula + SQL/index plan for your current schema next.