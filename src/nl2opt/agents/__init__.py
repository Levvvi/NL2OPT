__all__ = [
    "ExtractorResult",
    "DeepSeekClient",
    "LLMClient",
    "LLMResponse",
    "MockLLMClient",
    "RouterResult",
    "build_extractor_prompt",
    "extract_problem_spec",
    "get_schema_model_for_problem_type",
    "parse_json_object",
    "route_text",
    "validate_spec_dict",
]


def __getattr__(name: str):
    if name in {"RouterResult", "route_text"}:
        from nl2opt.agents.router import RouterResult, route_text

        exports = {
            "RouterResult": RouterResult,
            "route_text": route_text,
        }
        return exports[name]
    if name in {"DeepSeekClient", "LLMClient", "LLMResponse", "MockLLMClient"}:
        from nl2opt.agents.llm_client import DeepSeekClient, LLMClient, LLMResponse, MockLLMClient

        exports = {
            "DeepSeekClient": DeepSeekClient,
            "LLMClient": LLMClient,
            "LLMResponse": LLMResponse,
            "MockLLMClient": MockLLMClient,
        }
        return exports[name]
    if name == "build_extractor_prompt":
        from nl2opt.agents.prompts import build_extractor_prompt

        return build_extractor_prompt
    if name in {
        "ExtractorResult",
        "extract_problem_spec",
        "get_schema_model_for_problem_type",
        "parse_json_object",
        "validate_spec_dict",
    }:
        from nl2opt.agents.extractor import (
            ExtractorResult,
            extract_problem_spec,
            get_schema_model_for_problem_type,
            parse_json_object,
            validate_spec_dict,
        )

        exports = {
            "ExtractorResult": ExtractorResult,
            "extract_problem_spec": extract_problem_spec,
            "get_schema_model_for_problem_type": get_schema_model_for_problem_type,
            "parse_json_object": parse_json_object,
            "validate_spec_dict": validate_spec_dict,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
