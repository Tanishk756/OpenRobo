# ADR-0004: AI Provider Abstraction and Local-First Architecture

- **Status**: Proposed
- **Date**: 2026-08-31
- **Authors**: OpenRobo Architecture Team

## Context

OpenRobo aims to offer AI-assisted discovery, stack recommendations, and robotics troubleshooting while upholding core principles:
1. AI must be **optional** — all core registry, search, compatibility, and CLI features work 100% without AI.
2. AI-provider **neutrality** — no lock-in to OpenAI, Anthropic, Google, or any single vendor.
3. **Local-first & Zero-cost** — support self-hosted/local LLMs (Ollama, llama.cpp, Nemotron, Qwen, Llama 3) via standard OpenAI-compatible endpoints.

## Decision

1. **AI Abstraction Interface (`AIProvider`)**:
   Define an abstract interface in python backend:
   ```python
   class AIProvider(ABC):
       async def generate_summary(self, resource: Resource) -> str: ...
       async def recommend_stack(self, request: StackRequest, context: List[Resource]) -> StackRecommendation: ...
       async def explain_compatibility(self, result: CompatibilityResult) -> str: ...
   ```
2. **Implementations**:
   - `NoOpAIProvider`: Default fallback when AI is disabled. Returns deterministic rule-based output.
   - `OpenAICompatibleProvider`: Configurable provider connecting to local instances (Ollama, vLLM, LM Studio) or cloud endpoints (OpenAI, DeepSeek, Groq) via base URL & API key.
   - `GoogleGenAIProvider`: Optional provider for Gemini APIs.
3. **Grounding & Attribution Rules**:
   - AI outputs MUST separate structured output into `FACT`, `INFERENCE`, `RECOMMENDATION`, and `UNKNOWN`.
   - All AI responses must explicitly cite OpenRobo Resource IDs used in the context prompt.

## Consequences

### Positive
- Fully functional without any external AI service or API key.
- End-users can run local LLMs on their own hardware for offline operations.
- Zero mandatory vendor cost.

### Negative / Trade-offs
- AI prompts and RAG output formatting require strict validation to prevent LLM hallucinations.
