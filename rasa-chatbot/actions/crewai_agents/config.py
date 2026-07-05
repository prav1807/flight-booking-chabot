from crewai import LLM


def get_llm() -> LLM:
    """Returns the shared LLM instance configured for local Ollama."""
    return LLM(
        model="ollama/qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0.1,
    )
