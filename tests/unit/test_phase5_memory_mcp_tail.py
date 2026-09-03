from src.services.graph_service import GraphService


def test_graph_node_manager_exposes_expected_aging_and_importance_methods(tmp_path):
    graph = GraphService(data_dir=str(tmp_path))
    assert graph.add_chunk_node("chunk:alpha", {"text": "alpha memory"})

    assert graph.increment_node_frequency("chunk:alpha") is True
    assert graph.update_node_decay_score("chunk:alpha") is True
    assert graph.update_node_importance("chunk:alpha", explicit_weight=0.9) is True

    node = graph.get_node("chunk:alpha")
    assert node["frequency"] == 1
    assert 0.0 <= node["decay_score"] <= 1.0
    assert 0.0 <= node["importance"] <= 1.0
    assert graph.get_nodes_by_importance(0.0, 1.0)[0][0] == "chunk:alpha"
