-- Day 5a: record which provider (and whether it was the fallback call) answered each LLM
-- call, plus Gemini's thinking-token count (its equivalent of Groq's reasoning_tokens, stored
-- separately since only one provider reports it per call).
ALTER TABLE llm_calls ADD COLUMN provider TEXT;
ALTER TABLE llm_calls ADD COLUMN thinking_tokens INTEGER;
ALTER TABLE llm_calls ADD COLUMN fallback_used INTEGER NOT NULL DEFAULT 0;
