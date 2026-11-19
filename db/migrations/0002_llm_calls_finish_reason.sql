-- Day 3c: record the provider's finish_reason (e.g. 'stop', 'length') and, when the provider
-- reports it separately, the reasoning-token count for each LLM call. tokens_out already
-- includes any reasoning tokens as a subtotal (confirmed against the real Groq API); this
-- column is the breakout, not an addition to tokens_out.
ALTER TABLE llm_calls ADD COLUMN finish_reason TEXT;
ALTER TABLE llm_calls ADD COLUMN reasoning_tokens INTEGER;
