"""Invoke all 14 MCP tools with real data."""
import asyncio
import sys
import os
import time

sys.path.insert(0, '.')
os.environ['OBSIDIAN_VAULT_PATH'] = os.environ.get('OBSIDIAN_VAULT_PATH', 'C:/Users/17175/OneDrive/Obsidian/DavidBrain')

from src.mcp.stdio_server import NexusSearchTool, handle_call_tool, load_config


def invoke_all_tools():
    print('=' * 60)
    print('INVOKING ALL 14 MCP TOOLS - REAL EXECUTION')
    print('=' * 60)

    # Load config and create the NexusSearchTool
    config = load_config()
    tool = NexusSearchTool(config)
    print(f'\nNexusSearchTool initialized with config')
    print(f'  Graph: {tool.graph_service.get_node_count()} nodes, {tool.graph_service.get_edge_count()} edges')
    print(f'  Obsidian vault: {tool._vault_path}')

    results = {}

    # Tool 1: vector_search
    print('\n[1/14] vector_search')
    try:
        result = handle_call_tool('vector_search', {'query': 'memory lifecycle management', 'limit': 3}, tool)
        results['vector_search'] = 'OK' if result.get('results') else 'EMPTY'
        print(f'  Result: {len(result.get("results", []))} matches found')
    except Exception as e:
        results['vector_search'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 2: unified_search
    print('\n[2/14] unified_search')
    try:
        result = handle_call_tool('unified_search', {'query': 'agent coordination', 'limit': 3}, tool)
        results['unified_search'] = 'OK' if result.get('results') or result.get('vector_results') else 'EMPTY'
        print(f'  Result: {result.get("total_results", 0)} total results')
    except Exception as e:
        results['unified_search'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 3: memory_store
    print('\n[3/14] memory_store')
    try:
        result = handle_call_tool('memory_store', {
            'text': f'Test memory entry for MCP tool validation - timestamp {time.time()}',
            'metadata': {'test': True, 'source': 'mcp_test', 'WHO': 'test-agent', 'PROJECT': 'memory-mcp', 'WHY': 'testing'}
        }, tool)
        # MCP response format: {"content": [...], "isError": False}
        results['memory_store'] = 'OK' if result.get('isError') == False else 'FAILED'
        content_text = result.get('content', [{}])[0].get('text', 'N/A')[:100]
        print(f'  Result: {content_text}')
    except Exception as e:
        results['memory_store'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 4: graph_query
    print('\n[4/14] graph_query')
    try:
        result = handle_call_tool('graph_query', {'query': 'memory', 'query_type': 'neighbors', 'limit': 5}, tool)
        results['graph_query'] = 'OK' if result.get('results') is not None else 'EMPTY'
        print(f'  Result: {len(result.get("results", []))} neighbors found')
    except Exception as e:
        results['graph_query'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 5: bayesian_inference
    print('\n[5/14] bayesian_inference')
    try:
        result = handle_call_tool('bayesian_inference', {
            'evidence': {'context': 'code_review', 'complexity': 'high'},
            'query': 'bug_probability'
        }, tool)
        results['bayesian_inference'] = 'OK' if result.get('inference') is not None or result.get('probability') is not None else 'EMPTY'
        print(f'  Result: inference={result}')
    except Exception as e:
        results['bayesian_inference'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 6: entity_extraction
    print('\n[6/14] entity_extraction')
    try:
        result = handle_call_tool('entity_extraction', {
            'text': 'The MemoryMCPServer class in stdio_server.py handles requests from Claude Code CLI using ChromaDB for vector storage.'
        }, tool)
        results['entity_extraction'] = 'OK' if result.get('entities') is not None else 'EMPTY'
        print(f'  Result: {len(result.get("entities", []))} entities extracted')
    except Exception as e:
        results['entity_extraction'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 7: mode_detection
    print('\n[7/14] mode_detection')
    try:
        result = handle_call_tool('mode_detection', {
            'query': 'What if we redesigned the entire memory architecture from scratch?'
        }, tool)
        results['mode_detection'] = 'OK' if result.get('mode') else 'EMPTY'
        print(f'  Result: mode={result.get("mode", "N/A")}, tokens={result.get("token_budget", "N/A")}')
    except Exception as e:
        results['mode_detection'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 8: hipporag_retrieve
    print('\n[8/14] hipporag_retrieve')
    try:
        result = handle_call_tool('hipporag_retrieve', {
            'query': 'How does memory consolidation work with graph relationships?',
            'limit': 3
        }, tool)
        results['hipporag_retrieve'] = 'OK' if result.get('results') is not None else 'EMPTY'
        print(f'  Result: {len(result.get("results", []))} multi-hop results')
    except Exception as e:
        results['hipporag_retrieve'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 9: detect_mode
    print('\n[9/14] detect_mode')
    try:
        result = handle_call_tool('detect_mode', {
            'query': 'Compare the performance of vector search vs graph search'
        }, tool)
        results['detect_mode'] = 'OK' if result.get('mode') else 'EMPTY'
        print(f'  Result: mode={result.get("mode", "N/A")}, tokens={result.get("token_budget", "N/A")}')
    except Exception as e:
        results['detect_mode'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 10: lifecycle_status
    print('\n[10/14] lifecycle_status')
    try:
        result = handle_call_tool('lifecycle_status', {}, tool)
        results['lifecycle_status'] = 'OK' if result.get('stages') or result.get('active') is not None else 'EMPTY'
        print(f'  Result: stages={result.get("stages", result)}')
    except Exception as e:
        results['lifecycle_status'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 11: obsidian_sync
    print('\n[11/14] obsidian_sync')
    try:
        result = handle_call_tool('obsidian_sync', {'action': 'status'}, tool)
        results['obsidian_sync'] = 'OK' if result.get('status') or result.get('vault_path') else 'EMPTY'
        print(f'  Result: vault={result.get("vault_path", "N/A")}, files={result.get("total_files", "N/A")}')
    except Exception as e:
        results['obsidian_sync'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 12: beads_ready_tasks
    print('\n[12/14] beads_ready_tasks')
    try:
        result = handle_call_tool('beads_ready_tasks', {'limit': 5}, tool)
        results['beads_ready_tasks'] = 'OK' if result.get('tasks') is not None else 'EMPTY'
        print(f'  Result: {len(result.get("tasks", []))} ready tasks')
    except Exception as e:
        results['beads_ready_tasks'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 13: beads_task_detail
    print('\n[13/14] beads_task_detail')
    try:
        result = handle_call_tool('beads_task_detail', {'task_id': 'TEST-001'}, tool)
        results['beads_task_detail'] = 'OK' if result.get('task') is not None or result.get('id') else 'EMPTY'
        print(f'  Result: task={result.get("task", result)}')
    except Exception as e:
        results['beads_task_detail'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Tool 14: beads_query_tasks
    print('\n[14/14] beads_query_tasks')
    try:
        result = handle_call_tool('beads_query_tasks', {'status': 'open', 'limit': 5}, tool)
        results['beads_query_tasks'] = 'OK' if result.get('tasks') is not None else 'EMPTY'
        print(f'  Result: {len(result.get("tasks", []))} tasks queried')
    except Exception as e:
        results['beads_query_tasks'] = f'ERROR: {e}'
        print(f'  ERROR: {e}')

    # Summary
    print('\n' + '=' * 60)
    print('SUMMARY - ALL 14 TOOLS INVOCATION RESULTS')
    print('=' * 60)

    ok_count = sum(1 for v in results.values() if v == 'OK')
    empty_count = sum(1 for v in results.values() if v == 'EMPTY')
    error_count = sum(1 for v in results.values() if str(v).startswith('ERROR'))

    for tool_name, status in results.items():
        icon = '[OK]' if status == 'OK' else ('[EMPTY]' if status == 'EMPTY' else '[ERR]')
        print(f'  {icon} {tool_name}: {status}')

    print(f'\nTOTAL: {ok_count} OK, {empty_count} EMPTY (valid), {error_count} ERRORS')
    print(f'SUCCESS RATE: {(ok_count + empty_count)}/{len(results)} = {(ok_count + empty_count) / len(results) * 100:.1f}%')

    return results


if __name__ == '__main__':
    invoke_all_tools()
