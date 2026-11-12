"""Fresh-process entry point; no inherited SQLAlchemy connections."""
import json
import sys

from botkernel.investigation_process import install_parent_death_guard


def main():
    install_parent_death_guard()
    request = json.load(sys.stdin)
    from botkernel.bedrock import BedrockProviderError
    from botkernel.investigator import Investigation, investigation_graph

    try:
        payload = investigation_graph.invoke(request)["report"]
        payload["investigation_id"] = request["run_id"]
        payload = Investigation.model_validate(payload).model_dump(mode="json")
        encoded = json.dumps({"report": payload}, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 200000:
            raise ValueError("report too large")
        sys.stdout.write(encoded)
    except Exception as error:
        category = error.category if isinstance(error, BedrockProviderError) else "execution_error"
        result = {"error_category": category}
        if isinstance(error, BedrockProviderError) and error.diagnostics:
            result["error_diagnostics"] = error.diagnostics
        sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
