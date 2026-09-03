#!/usr/bin/env python
"""Exercise the four Bayesian handler outcomes."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
GATE_ID = "P1a"
TOKEN = "BAYESIAN_HONESTY_OK no_network=1 unknown_node=1 none_result=1 positive=1"


def probe(fixture) -> bool:
    return all(fixture.get(key) for key in ("no_network", "unknown_node", "none_result", "positive"))


def _planted_bad_fixture():
    good = {"no_network": True, "unknown_node": True, "none_result": True, "positive": True}
    return [{**good, key: False} for key in good]


def _real_fixture():
    from src.mcp.request_router import handle_bayesian_inference

    tool = MagicMock()
    tool.nexus_processor.probabilistic_query_engine = MagicMock()
    tool.nexus_processor._extract_query_entity.return_value = "known"
    tool.graph_service = MagicMock()

    tool._build_bayesian_network.return_value = None
    no_network = bool(handle_bayesian_inference({"query": "known"}, tool).get("isError"))

    network = MagicMock()
    network.nodes.return_value = []
    tool._build_bayesian_network.return_value = network
    unknown = bool(handle_bayesian_inference({"query": "known"}, tool).get("isError"))

    network.nodes.return_value = ["known"]
    tool.nexus_processor.probabilistic_query_engine.query_conditional.return_value = None
    none_result = bool(handle_bayesian_inference({"query": "known"}, tool).get("isError"))

    tool.nexus_processor.probabilistic_query_engine.query_conditional.return_value = {"results": {}}
    positive = not bool(handle_bayesian_inference({"query": "known"}, tool).get("isError"))
    return {"no_network": no_network, "unknown_node": unknown, "none_result": none_result, "positive": positive}


def self_test() -> bool:
    for bad in _planted_bad_fixture():
        assert not probe(bad)
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        self_test_ok = self_test()
        if not self_test_ok:
            return 1
        print(f"SELF_TEST_REJECTED {GATE_ID}")
        return 0
    result = _real_fixture()
    ok = probe(result)
    if not ok:
        return 1
    print(TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
