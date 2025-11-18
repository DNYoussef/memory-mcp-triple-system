#!/usr/bin/env python3
"""
Knowledge Base Population Script for Memory MCP Triple System

This script populates the memory system with comprehensive knowledge about:
1. All 11 MCP servers (4 local + 7 free Anthropic/Microsoft)
2. Connascence-Analyzer system (complete documentation)
3. Three-tier plugin architecture (skills, agents, slash commands)
4. Meta-level components (meta-skills, meta-agents, meta-commands)
5. CLAUDE.md knowledge and conventions
6. Integration patterns and workflows

Date: 2025-11-01
Version: 3.0.4
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.memory.core import MemorySystem
from src.memory.layered_store import LayeredMemoryStore


class KnowledgeBasePopulator:
    """Populate memory system with comprehensive knowledge"""

    def __init__(self):
        self.memory = MemorySystem()
        self.timestamp = datetime.utcnow().isoformat()
        self.project = "ruv-sparc-three-loop-system"

    async def populate_all(self):
        """Populate all knowledge categories"""
        print("=== Starting Knowledge Base Population ===\n")

        await self.populate_mcp_servers()
        await self.populate_connascence_system()
        await self.populate_plugin_architecture()
        await self.populate_meta_components()
        await self.populate_claude_md_knowledge()
        await self.populate_integration_patterns()

        print("\n=== Knowledge Base Population Complete ===")

    # ========== MCP SERVERS KNOWLEDGE ==========

    async def populate_mcp_servers(self):
        """Populate knowledge about all 11 MCP servers"""
        print("📦 Populating MCP Servers knowledge...")

        mcp_servers = {
            # LOCAL SERVERS (4)
            "connascence-analyzer": {
                "type": "local_python",
                "location": "C:\\Users\\17175\\Desktop\\connascence\\",
                "command": "venv-connascence\\Scripts\\python.exe -u mcp/cli.py mcp-server",
                "purpose": "Code quality analysis with 9 connascence types and NASA compliance",
                "tools": ["analyze_file", "analyze_workspace", "health_check"],
                "performance": "0.018 seconds per file",
                "agents": ["coder", "reviewer", "tester", "code-analyzer", "functionality-audit",
                          "theater-detection-audit", "production-validator", "sparc-coder", "analyst",
                          "backend-dev", "mobile-dev", "ml-developer", "base-template-generator", "code-review-swarm"],
                "capabilities": [
                    "Detect 9 connascence types (Name, Type, Meaning, Position, Algorithm, Execution, Timing, Value, Identity)",
                    "Identify 7+ violation categories (God Objects, Parameter Bombs, Complexity, Deep Nesting, Long Lines, Missing Docstrings, Naming Violations)",
                    "NASA Power of 10 Rules compliance checking",
                    "Real-time code quality metrics",
                    "Pattern detection and learning"
                ],
                "workflow": """
                1. Start analysis: connascence-analyzer.analyze_file(file_path, analysis_type='full')
                2. Review violations: Check for God Objects, Parameter Bombs, complexity issues
                3. Fix violations: Apply NASA Rule 10 principles
                4. Verify: Re-analyze to confirm 0 violations
                5. Store patterns: memory-mcp.memory_store(pattern, {intent: 'analysis'})
                """
            },

            "memory-mcp": {
                "type": "local_python",
                "location": "C:\\Users\\17175\\Desktop\\memory-mcp-triple-system\\",
                "command": "venv-memory\\Scripts\\python.exe -u -m src.mcp.stdio_server",
                "purpose": "Persistent cross-session memory with triple-layer retention (24h/7d/30d+)",
                "tools": ["vector_search", "memory_store"],
                "storage": "Local ChromaDB with 384-dimensional vectors and HNSW indexing",
                "agents": "ALL 90 agents (global access)",
                "capabilities": [
                    "Triple-layer memory architecture (short-term/mid-term/long-term)",
                    "Mode-aware context adaptation (Execution/Planning/Brainstorming)",
                    "Semantic vector search with ChromaDB",
                    "Automatic tagging protocol (WHO/WHEN/PROJECT/WHY)",
                    "Self-referential memory (can retrieve its own documentation)",
                    "Pattern-based mode detection (29 regex patterns, 85%+ accuracy)",
                    "Curated core results (5 core + variable extended results)"
                ],
                "tagging_protocol": {
                    "WHO": "Agent name, category, capabilities",
                    "WHEN": "ISO/Unix/readable timestamps",
                    "PROJECT": "Auto-detected from working directory",
                    "WHY": "8 intent categories (implementation, bugfix, refactor, testing, documentation, analysis, planning, research)"
                },
                "workflow": """
                1. Store: memory-mcp.memory_store(text, metadata={agent, project, intent, layer})
                2. Retrieve: memory-mcp.vector_search(query, limit=10)
                3. Tag properly: Include WHO/WHEN/PROJECT/WHY in metadata
                4. Choose layer: short_term (24h), mid_term (7d), long_term (30d+)
                """
            },

            "focused-changes": {
                "type": "local_nodejs",
                "location": "C:\\Users\\17175\\Documents\\Cline\\MCP\\focused-changes-server\\",
                "command": "node build/index.js",
                "purpose": "Track file changes, ensure focused scope, build error trees from test failures",
                "tools": ["start_tracking", "analyze_changes", "root_cause_analysis"],
                "agents": ["coder", "reviewer", "tester", "sparc-coder", "functionality-audit"],
                "capabilities": [
                    "Track file changes to detect scope creep",
                    "Analyze proposed changes for focus",
                    "Build error tree diagrams from test logs",
                    "Root cause analysis for test failures",
                    "Scope verification and enforcement"
                ],
                "workflow": """
                1. Start: focused-changes.start_tracking(filepath, initial_content)
                2. Work: Make focused changes to the file
                3. Verify: focused-changes.analyze_changes(newContent)
                4. Debug: focused-changes.root_cause_analysis(testResults) if tests fail
                5. Store: memory-mcp.memory_store(scope_verification, {intent: 'testing'})
                """
            },

            "ToC": {
                "type": "local_nodejs",
                "location": "C:\\Users\\17175\\Documents\\Cline\\MCP\\toc-server\\",
                "command": "node build/index.js",
                "purpose": "Generate table of contents for documentation (Python, Markdown, JSON, YAML, TXT)",
                "tools": ["generate_toc", "get_file_description"],
                "agents": ["api-docs", "documentation specialists", "architecture planners"],
                "capabilities": [
                    "Generate hierarchical TOC for Python files (from docstrings, classes, functions)",
                    "Generate TOC for Markdown files (from headings)",
                    "Support for JSON, YAML, TXT files",
                    "Filter hidden files, __pycache__, node_modules, .log files",
                    "Extract descriptions from docstrings"
                ],
                "workflow": """
                1. Generate: ToC.generate_toc(directory_path, file_type)
                2. Get description: ToC.get_file_description(file_path)
                3. Use in docs: Include TOC in documentation generation
                4. Store: memory-mcp.memory_store(toc_structure, {intent: 'documentation'})
                """
            },

            # FREE ANTHROPIC/MICROSOFT SERVERS (7)

            "markitdown": {
                "type": "free_microsoft_python",
                "command": "markitdown-mcp",
                "purpose": "Convert 29+ file formats (PDF, Office, images, audio, archives) to Markdown",
                "agents": ["Documentation specialists", "content processors"],
                "capabilities": [
                    "Convert PDFs to clean Markdown",
                    "Extract text from Office docs (Word, Excel, PowerPoint)",
                    "Convert images to Markdown (with OCR support)",
                    "Convert audio files to text (speech recognition)",
                    "Extract from archives (ZIP, TAR, etc.)",
                    "Preserve document structure and formatting"
                ],
                "workflow": """
                1. Convert: markitdown.convert(file_path, output_format='markdown')
                2. Process: Review and clean up converted Markdown
                3. Store: memory-mcp.memory_store(converted_docs, {intent: 'documentation'})
                """
            },

            "playwright": {
                "type": "free_microsoft_nodejs",
                "command": "npx @playwright/mcp@latest",
                "purpose": "Browser automation for web testing and scraping using Playwright",
                "agents": ["tester", "web-research specialists"],
                "capabilities": [
                    "Automated browser testing (Chromium, Firefox, WebKit)",
                    "Web scraping with accessibility snapshots",
                    "Screenshot and PDF generation",
                    "Form filling and interaction automation",
                    "Network interception and mocking",
                    "Cross-browser testing"
                ],
                "workflow": """
                1. Launch: playwright.launch(browser='chromium', headless=true)
                2. Navigate: playwright.goto(url)
                3. Interact: playwright.click(selector) / playwright.fill(selector, text)
                4. Assert: playwright.expect(selector).toContain(text)
                5. Store: memory-mcp.memory_store(test_results, {intent: 'testing'})
                """
            },

            "sequential-thinking": {
                "type": "free_anthropic_nodejs",
                "command": "npx -y @modelcontextprotocol/server-sequential-thinking",
                "purpose": "Dynamic problem-solving through structured thought sequences",
                "agents": ["planner", "researcher", "system-architect", "specification", "architecture"],
                "capabilities": [
                    "Break down complex problems into steps",
                    "Revise and refine thinking as understanding deepens",
                    "Structured reasoning with thought chains",
                    "Multi-step problem decomposition",
                    "Reflective problem-solving"
                ],
                "workflow": """
                1. Start: sequential-thinking.process(problem, context)
                2. Decompose: Break problem into sequential steps
                3. Refine: Revise thinking based on new insights
                4. Conclude: Synthesize solution from thought sequence
                5. Store: memory-mcp.memory_store(solution, {intent: 'planning', sparc_phase: 'specification'})
                """
            },

            "fetch": {
                "type": "free_anthropic_nodejs",
                "command": "npx -y @modelcontextprotocol/server-fetch",
                "purpose": "Web content fetching and conversion for efficient LLM usage",
                "agents": ["researcher", "planner"],
                "capabilities": [
                    "Fetch web content with HTTP/HTTPS support",
                    "Convert HTML to clean Markdown",
                    "Extract main content (remove ads, navigation)",
                    "Handle redirects and authentication",
                    "Support for custom headers"
                ],
                "workflow": """
                1. Fetch: fetch.get(url, options)
                2. Convert: Automatically converts HTML to Markdown
                3. Extract: Gets main content only
                4. Store: memory-mcp.memory_store(web_content, {intent: 'research'})
                """
            },

            "filesystem": {
                "type": "free_anthropic_nodejs",
                "command": "npx -y @modelcontextprotocol/server-filesystem C:/Users/17175/claude-code-plugins",
                "purpose": "Secure file operations with configurable access controls",
                "agents": "ALL agents needing file I/O beyond Claude Code's built-in tools",
                "capabilities": [
                    "Read files with permission control",
                    "Write files securely",
                    "List directory contents",
                    "Path-based access controls",
                    "Restricted to allowed directories only"
                ],
                "workflow": """
                1. Read: filesystem.read(file_path)
                2. Write: filesystem.write(file_path, content)
                3. List: filesystem.list(directory_path)
                4. Always check: Verify file is in allowed directory
                """
            },

            "git": {
                "type": "free_anthropic_nodejs",
                "command": "npx -y @modelcontextprotocol/server-git",
                "purpose": "Git repository operations (local only, no API required)",
                "agents": ["github-modes", "pr-manager", "release-manager", "repo-architect"],
                "capabilities": [
                    "Read Git repository status",
                    "Search Git history",
                    "Get file contents from Git",
                    "View commit logs",
                    "No API keys required (local operations only)"
                ],
                "workflow": """
                1. Status: git.status(repo_path)
                2. Log: git.log(repo_path, options)
                3. Show: git.show(commit_hash)
                4. Search: git.search(query, repo_path)
                5. Store: memory-mcp.memory_store(git_history, {intent: 'analysis'})
                """
            },

            "time": {
                "type": "free_anthropic_nodejs",
                "command": "npx -y @modelcontextprotocol/server-time",
                "purpose": "Time and timezone conversion capabilities",
                "agents": ["Scheduling", "planning", "time-sensitive workflows"],
                "capabilities": [
                    "Get current time in any timezone",
                    "Convert between timezones",
                    "Format dates and times",
                    "Calculate time differences",
                    "Support for all IANA timezones"
                ],
                "workflow": """
                1. Get time: time.now(timezone='UTC')
                2. Convert: time.convert(timestamp, from_tz, to_tz)
                3. Format: time.format(timestamp, format_string)
                4. Use in: Scheduling, deadlines, time-sensitive operations
                """
            }
        }

        # Store each MCP server's knowledge
        for server_name, server_info in mcp_servers.items():
            knowledge_text = f"""
            MCP SERVER: {server_name}

            TYPE: {server_info['type']}
            COMMAND: {server_info['command']}
            PURPOSE: {server_info['purpose']}

            AGENTS: {', '.join(server_info['agents']) if isinstance(server_info['agents'], list) else server_info['agents']}

            CAPABILITIES:
            {chr(10).join(f"- {cap}" for cap in server_info['capabilities'])}

            WORKFLOW:
            {server_info['workflow']}

            STATUS: Installed and configured in Claude Code (v3.0.4)
            LOCATION: {server_info.get('location', 'N/A')}
            TOOLS: {', '.join(server_info.get('tools', []))}
            """

            metadata = {
                "agent": "knowledge-base-populator",
                "category": "mcp-server-documentation",
                "project": self.project,
                "intent": "documentation",
                "layer": "long_term",
                "mcp_server": server_name,
                "server_type": server_info['type'],
                "timestamp": self.timestamp,
                "keywords": ["mcp", "server", server_name, "tools", "capabilities"]
            }

            await self.memory.store(knowledge_text, metadata)
            print(f"  ✓ Stored {server_name} knowledge")

        # Store MCP server summary
        summary_text = """
        MCP SERVERS COMPREHENSIVE SUMMARY

        Total Installed: 11 FREE servers (no API keys, no payment required)

        LOCAL SERVERS (4):
        1. connascence-analyzer - Code quality analysis
        2. memory-mcp - Persistent memory with triple-layer retention
        3. focused-changes - File change tracking and scope enforcement
        4. ToC - Documentation table of contents generation

        FREE ANTHROPIC/MICROSOFT SERVERS (7):
        5. markitdown (Microsoft) - Convert 29+ file formats to Markdown
        6. playwright (Microsoft) - Browser automation for web testing
        7. sequential-thinking (Anthropic) - Dynamic problem-solving
        8. fetch (Anthropic) - Web content fetching
        9. filesystem (Anthropic) - Secure file operations
        10. git (Anthropic) - Git repository operations (local only)
        11. time (Anthropic) - Time and timezone conversion

        EXCLUDED SERVERS (Require Payment/API Keys):
        - Context7 (requires Upstash API key)
        - GitHub MCP (requires GITHUB_TOKEN - use git server instead)
        - HuggingFace, DeepWiki, Ref (packages don't exist)

        CONFIGURATION:
        - All servers added to C:\\Users\\17175\\.claude.json
        - Agent registry updated for all 90 agents
        - Each agent has specific usage instructions
        - All references to non-existing servers removed

        INTEGRATION PHILOSOPHY:
        - FREE ONLY: 100% free (no payment, no API keys, no account registration)
        - LOCAL FIRST: Prefer local processing over cloud services
        - PRIVACY: No data sent to third-party services
        - SIMPLICITY: Simple installation via claude mcp add commands
        - COMPREHENSIVE: 11 servers covering all major use cases
        """

        await self.memory.store(summary_text, {
            "agent": "knowledge-base-populator",
            "category": "mcp-summary",
            "project": self.project,
            "intent": "documentation",
            "layer": "long_term",
            "timestamp": self.timestamp,
            "keywords": ["mcp", "summary", "servers", "installation", "configuration"]
        })

        print("  ✓ Stored MCP servers summary\n")


    # ========== CONNASCENCE SYSTEM KNOWLEDGE ==========

    async def populate_connascence_system(self):
        """Populate comprehensive connascence-analyzer knowledge"""
        print("🔍 Populating Connascence System knowledge...")

        connascence_knowledge = """
        CONNASCENCE SAFETY ANALYZER - COMPREHENSIVE DOCUMENTATION

        Repository: https://github.com/DNYoussef/connascence-safety-analyzer
        Location: C:\\Users\\17175\\Desktop\\connascence\\
        Type: Local Python MCP Server
        Version: Production Ready
        Performance: 0.018 seconds per file

        PURPOSE:
        Advanced code quality analysis tool that detects 9 connascence types and 7+ violation
        categories, with NASA Power of 10 Rules compliance checking.

        9 CONNASCENCE TYPES:

        1. **Connascence of Name (CoN)**: Multiple components must agree on the name of an entity
           - Example: Variable names, function names, class names
           - Impact: Renaming requires changing all references

        2. **Connascence of Type (CoT)**: Multiple components must agree on the type of an entity
           - Example: Function parameters, return types
           - Impact: Type changes propagate to all usages

        3. **Connascence of Meaning (CoM)**: Multiple components must agree on the meaning of values
           - Example: Magic numbers, boolean flags, enums
           - Impact: Meaning changes require understanding all contexts

        4. **Connascence of Position (CoP)**: Multiple components must agree on the order of values
           - Example: Function arguments, array indices
           - Impact: Order changes break all call sites

        5. **Connascence of Algorithm (CoA)**: Multiple components must agree on a particular algorithm
           - Example: Hash functions, encryption algorithms
           - Impact: Algorithm changes require synchronized updates

        6. **Connascence of Execution (CoE)**: The order of execution of components is important
           - Example: Initialization order, sequence dependencies
           - Impact: Execution order changes cause failures

        7. **Connascence of Timing (CoT)**: The timing of execution of components is important
           - Example: Race conditions, deadlocks
           - Impact: Timing changes cause intermittent failures

        8. **Connascence of Value (CoV)**: Several values must change together
           - Example: Related configuration values
           - Impact: Partial updates cause inconsistency

        9. **Connascence of Identity (CoI)**: Multiple components must reference the same entity
           - Example: Singleton patterns, shared state
           - Impact: Identity changes break references

        7+ VIOLATION CATEGORIES:

        1. **God Objects**: Classes with too many responsibilities (>500 lines, >20 methods)
        2. **Parameter Bombs**: Functions with too many parameters (>4 parameters)
        3. **Cyclomatic Complexity**: Functions with too many branches (>10 complexity)
        4. **Deep Nesting**: Code with excessive nesting levels (>4 levels)
        5. **Long Lines**: Lines exceeding 88 characters (PEP 8 compliance)
        6. **Missing Docstrings**: Classes/functions without documentation
        7. **Naming Violations**: Non-compliant naming conventions

        NASA POWER OF 10 RULES:

        1. Restrict all code to very simple control flow constructs
        2. Give all loops a fixed upper bound
        3. Do not use dynamic memory allocation after initialization
        4. No function should be longer than what can be printed on a single sheet (60 lines)
        5. Code should have a minimum of two assertions per function
        6. Data objects must be declared at the smallest possible level of scope
        7. Each calling function must check non-void function return values
        8. The use of the preprocessor must be limited to file inclusion and simple macros
        9. The use of pointers should be restricted
        10. All code must be compiled with all compiler warnings enabled

        TOOLS PROVIDED:

        1. **analyze_file(file_path, analysis_type)**
           - Analyze single file for all violations
           - Returns: violations, metrics, connascence types detected
           - Performance: 0.018s per file

        2. **analyze_workspace(workspace_path, file_patterns)**
           - Batch analysis of multiple files
           - Returns: aggregate metrics, violation summary
           - Supports: Python, JavaScript, TypeScript

        3. **health_check()**
           - Verify server is running
           - Returns: status, version, capabilities

        USAGE WORKFLOW:

        FOR CODER AGENT:
        1. Start tracking: focused-changes.start_tracking(file)
        2. Write code
        3. Analyze quality: connascence-analyzer.analyze_file(file, 'full')
        4. Fix violations before committing
        5. Store decisions: memory-mcp.memory_store(decision, {intent: 'implementation'})
        6. Verify changes: focused-changes.analyze_changes(newContent)

        FOR REVIEWER AGENT:
        1. Run quality check: connascence-analyzer.analyze_workspace(files)
        2. Check change scope: focused-changes.analyze_changes(changes)
        3. Store findings: memory-mcp.memory_store(findings, {intent: 'analysis'})
        4. Verify 0 violations before approval

        FOR TESTER AGENT:
        1. If tests fail: focused-changes.root_cause_analysis(testResults)
        2. Analyze test code: connascence-analyzer.analyze_file(test_file)
        3. Store patterns: memory-mcp.memory_store(pattern, {intent: 'testing'})
        4. Track coverage trends in memory

        INTEGRATION WITH MEMORY-MCP:
        - All analysis results should be stored with intent='analysis'
        - Violation patterns should be tagged with 'connascence' keyword
        - Use layer='mid_term' for temporary violation tracking
        - Use layer='long_term' for learned patterns and best practices

        AGENTS WITH ACCESS (14 total):
        coder, reviewer, tester, code-analyzer, functionality-audit, theater-detection-audit,
        production-validator, sparc-coder, analyst, backend-dev, mobile-dev, ml-developer,
        base-template-generator, code-review-swarm
        """

        await self.memory.store(connascence_knowledge, {
            "agent": "knowledge-base-populator",
            "category": "connascence-documentation",
            "project": self.project,
            "intent": "documentation",
            "layer": "long_term",
            "timestamp": self.timestamp,
            "keywords": ["connascence", "code-quality", "nasa", "violations", "analysis"]
        })

        print("  ✓ Stored comprehensive connascence system knowledge\n")


    # ========== PLUGIN ARCHITECTURE KNOWLEDGE ==========

    async def populate_plugin_architecture(self):
        """Populate three-tier plugin architecture knowledge"""
        print("🏗️  Populating Plugin Architecture knowledge...")

        architecture_knowledge = """
        THREE-TIER CLAUDE CODE/CLAUDE-FLOW PLUGIN ARCHITECTURE

        Repository: https://github.com/DNYoussef/ruv-sparc-three-loop-system
        Location: C:\\Users\\17175\\claude-code-plugins\\ruv-sparc-three-loop-system
        Version: 3.0.4
        Type: Multi-part Claude Code plugin with Claude-Flow integration

        ARCHITECTURE OVERVIEW:

        The system implements a three-tier architecture that combines:
        - Claude Code's built-in plugin system (skills, agents, slash commands)
        - Claude-Flow's MCP-based orchestration (swarm coordination, memory, hooks)
        - Meta-level components that create and manage the base-level components

        TIER 1: BASE COMPONENTS

        1. **Skills** (60+ total)
           - Location: .claude/skills/
           - Purpose: Reusable, composable workflow templates
           - Format: YAML frontmatter + Markdown content
           - Examples:
             * agent-creator: Create specialized agents with optimized prompts
             * functionality-audit: Validate code actually works
             * theater-detection-audit: Detect theater code
             * code-review-assistant: Comprehensive PR reviews
             * feature-dev-complete: Full feature lifecycle

        2. **Agents** (90+ total)
           - Location: agents/registry.json
           - Purpose: Specialized AI personalities for specific tasks
           - Categories:
             * Core Development: coder, reviewer, tester, planner, researcher
             * Swarm Coordination: hierarchical-coordinator, mesh-coordinator, adaptive-coordinator
             * Consensus: byzantine-coordinator, raft-manager, gossip-coordinator
             * Performance: perf-analyzer, performance-benchmarker
             * GitHub: github-modes, pr-manager, code-review-swarm, issue-tracker
             * SPARC: sparc-coord, specification, pseudocode, architecture, refinement
             * Specialized: backend-dev, mobile-dev, ml-developer, cicd-engineer

        3. **Slash Commands** (30+ total)
           - Location: .claude/commands/
           - Purpose: Quick-access prompts and workflows
           - Examples:
             * /sparc: Full SPARC methodology workflow
             * /audit-pipeline: Complete quality validation
             * /quick-check: Fast quality check
             * /claude-flow-swarm: Multi-agent coordination
             * /claude-flow-memory: Memory system interaction

        TIER 2: ORCHESTRATION LAYER (Claude-Flow Integration)

        1. **MCP Servers** (11 total)
           - claude-flow, ruv-swarm, flow-nexus (coordination)
           - memory-mcp, connascence-analyzer, focused-changes, ToC (local tools)
           - markitdown, playwright, sequential-thinking, fetch, filesystem, git, time (free tools)

        2. **Swarm Coordination**
           - Topologies: mesh, hierarchical, ring, star
           - Strategies: balanced, specialized, adaptive
           - Features: Agent spawning, task orchestration, memory sharing

        3. **Memory System**
           - Triple-layer retention (24h/7d/30d+)
           - Mode-aware adaptation (Execution/Planning/Brainstorming)
           - Automatic tagging (WHO/WHEN/PROJECT/WHY)
           - Semantic vector search with ChromaDB

        4. **Hooks System**
           - Pre-task, post-task lifecycle events
           - Pre-edit, post-edit file operations
           - Session-start, session-end management
           - Auto-formatting, neural training, metrics tracking

        TIER 3: META COMPONENTS

        These components create, modify, and manage Tier 1 & 2 components:

        1. **Meta-Skills**
           - agent-creator: Creates new specialized agents
           - skill-builder: Creates new skills with YAML frontmatter
           - micro-skill-creator: Creates atomic, focused skills
           - cascade-orchestrator: Creates multi-skill workflows
           - prompt-architect: Creates optimized prompts

        2. **Meta-Agents**
           - system-architect: Designs overall architecture
           - migration-planner: Plans system migrations
           - skill-forge: Forges new skills from requirements
           - intent-analyzer: Analyzes user intent for agent selection

        3. **Meta-Commands**
           - /plugin: Plugin management (install, enable, disable)
           - /agents: Agent management and creation
           - /sparc: Meta-workflow orchestration

        INTEGRATION PATTERNS:

        1. **Skill → Agent → Command**
           - Skill defines workflow
           - Agent executes with personality
           - Command provides quick access

        2. **MCP → Memory → Hooks**
           - MCP tools provide capabilities
           - Memory persists knowledge
           - Hooks automate coordination

        3. **Meta → Create → Execute**
           - Meta-component analyzes need
           - Creates base component
           - Executes workflow

        WORKFLOW EXAMPLE: Full Feature Development

        1. User: "/sparc implement authentication system"
        2. Meta-level: intent-analyzer determines requirements
        3. Orchestration: swarm-init creates mesh topology
        4. Base-level: Spawns agents (researcher, architect, coder, tester)
        5. Execution:
           - researcher: Uses sequential-thinking + memory-mcp
           - architect: Uses ToC + memory-mcp
           - coder: Uses connascence-analyzer + focused-changes + memory-mcp
           - tester: Uses playwright + focused-changes + memory-mcp
        6. Coordination: Hooks trigger for formatting, memory storage
        7. Result: Fully implemented, tested, documented feature

        KEY CONVENTIONS:

        1. **Skills**
           - Always use YAML frontmatter
           - Include examples and error handling
           - Reference agents by type

        2. **Agents**
           - Defined in agents/registry.json
           - Have mcp_servers.required arrays
           - Include specific usage instructions

        3. **Slash Commands**
           - Located in .claude/commands/
           - Can invoke skills and agents
           - Support arguments and @-mentions

        4. **Memory Tagging**
           - WHO: Agent name
           - WHEN: Timestamp
           - PROJECT: Auto-detected
           - WHY: Intent category

        DIRECTORY STRUCTURE:

        ruv-sparc-three-loop-system/
        ├── .claude/
        │   ├── commands/          # Slash commands
        │   ├── skills/            # Skills (YAML)
        │   └── settings.json      # Configuration
        ├── agents/
        │   ├── registry.json      # All 90 agents
        │   └── *.js               # Agent utilities
        ├── hooks/
        │   └── 12fa/              # Hook implementations
        ├── docs/                  # Documentation
        ├── security/              # Security components
        └── plugins/               # Plugin packages

        VERSION HISTORY:
        - v1.0: Initial SPARC implementation
        - v2.0: Security hardening
        - v3.0: Plugin marketplace
        - v3.0.4: MCP servers installed (current)
        """

        await self.memory.store(architecture_knowledge, {
            "agent": "knowledge-base-populator",
            "category": "architecture-documentation",
            "project": self.project,
            "intent": "documentation",
            "layer": "long_term",
            "timestamp": self.timestamp,
            "keywords": ["architecture", "plugins", "skills", "agents", "commands", "meta", "three-tier"]
        })

        print("  ✓ Stored plugin architecture knowledge\n")


    # ========== META COMPONENTS KNOWLEDGE ==========

    async def populate_meta_components(self):
        """Populate meta-level components knowledge"""
        print("🎯 Populating Meta Components knowledge...")

        meta_knowledge = """
        META-LEVEL COMPONENTS - SELF-MODIFYING SYSTEM

        Meta-components are higher-order components that create, modify, and manage
        the base-level skills, agents, and slash commands.

        META-SKILLS (Creates Skills):

        1. **agent-creator**
           - Purpose: Create specialized agents with optimized system prompts
           - Method: 4-phase SOP methodology from Desktop .claude-flow
           - Techniques: Evidence-based prompting, self-consistency, program-of-thought
           - Output: Fully specified agent in agents/registry.json
           - Usage: When new specialized agent needed

        2. **skill-builder**
           - Purpose: Create new Claude Code skills with proper YAML frontmatter
           - Method: Progressive disclosure structure
           - Output: Skill file in .claude/skills/
           - Usage: When new reusable workflow needed

        3. **micro-skill-creator**
           - Purpose: Create atomic, focused skills (one thing exceptionally well)
           - Method: Evidence-based prompting + functionality-audit validation
           - Output: Micro-skill with self-consistency patterns
           - Usage: Building composable workflow components

        4. **cascade-orchestrator**
           - Purpose: Create multi-skill workflows with parallel/sequential execution
           - Method: Workflow graph construction with dependencies
           - Output: Orchestrated cascade of skills
           - Usage: Complex multi-step workflows

        5. **prompt-architect**
           - Purpose: Analyze, create, and refine prompts using evidence-based techniques
           - Method: Structural optimization, self-consistency, anti-pattern detection
           - Output: Optimized prompts for any use case
           - Usage: Creating effective prompts for Claude/ChatGPT

        META-AGENTS (Creates Agents):

        1. **system-architect**
           - Purpose: Design overall system architecture and patterns
           - Creates: Architecture decisions, component designs
           - Stores: In memory-mcp with layer='long_term', sparc_phase='architecture'
           - Usage: High-level technical decisions

        2. **migration-planner**
           - Purpose: Plan comprehensive system migrations
           - Creates: Migration plans, compatibility matrices
           - Stores: In memory-mcp with intent='planning'
           - Usage: System upgrades and migrations

        3. **skill-forge**
           - Purpose: Forge new skills from high-level requirements
           - Creates: Complete skills with examples and error handling
           - Stores: Skill patterns in memory
           - Usage: Skill creation from natural language descriptions

        4. **intent-analyzer**
           - Purpose: Analyze user intent for optimal agent selection
           - Method: Cognitive science principles + probabilistic intent mapping
           - Output: Agent selection recommendations
           - Usage: Ambiguous requests, better understanding

        META-COMMANDS (Manages System):

        1. **/plugin**
           - Purpose: Plugin management (install, enable, disable, validate)
           - Subcommands:
             * /plugin install <name>: Install plugin from marketplace
             * /plugin enable <name>: Enable installed plugin
             * /plugin disable <name>: Disable plugin
             * /plugin marketplace: List available plugins
             * /plugin validate: Validate plugin structure
           - Usage: Managing the plugin system itself

        2. **/agents**
           - Purpose: Agent management and creation
           - Functions: List agents, create new agents, modify existing
           - Integration: With agent-creator skill
           - Usage: Dynamic agent creation

        3. **/sparc**
           - Purpose: Meta-workflow orchestration
           - Phases:
             * Specification: Requirements analysis
             * Pseudocode: Algorithm design
             * Architecture: System design
             * Refinement: TDD implementation
             * Completion: Integration
           - Usage: Systematic development workflows

        SELF-MODIFICATION PATTERNS:

        1. **Skill Self-Creation**
           - skill-builder creates new skills
           - New skills stored in .claude/skills/
           - Immediately available for use

        2. **Agent Self-Registration**
           - agent-creator creates new agents
           - Agents added to agents/registry.json
           - MCP server assignments automatic

        3. **Memory Self-Referential**
           - memory-mcp stores its own documentation
           - Can retrieve information about itself
           - Self-improving through pattern learning

        4. **Hook Self-Coordination**
           - Hooks can spawn new agents
           - Hooks can store patterns in memory
           - Hooks can modify workflow dynamically

        META-PROGRAMMING EXAMPLES:

        Example 1: Creating a New Skill
        ```
        User: "Create a skill for API documentation generation"
        Meta: skill-builder activated
        Process:
        1. Analyze requirements
        2. Generate YAML frontmatter
        3. Create workflow steps
        4. Add examples
        5. Write to .claude/skills/api-docs-generator.md
        Result: New skill immediately available
        ```

        Example 2: Creating a New Agent
        ```
        User: "Create an agent for Rust development"
        Meta: agent-creator activated
        Process:
        1. Research Rust best practices
        2. Design agent capabilities
        3. Create optimized system prompt
        4. Define MCP server requirements
        5. Add to agents/registry.json
        Result: New 'rust-developer' agent ready
        ```

        Example 3: Self-Improving Memory
        ```
        Agent: Stores successful pattern in memory
        Memory: Learns pattern
        Future: Pattern retrieved for similar task
        Result: Improved performance over time
        ```

        INTEGRATION WITH BASE COMPONENTS:

        Meta-Skills → Create → Base Skills
        Meta-Agents → Create → Base Agents
        Meta-Commands → Manage → System

        All meta-components use:
        - memory-mcp for pattern storage
        - connascence-analyzer for quality
        - focused-changes for scope control

        BEST PRACTICES:

        1. **Use meta-components when:**
           - Creating new reusable components
           - Modifying system behavior
           - Need self-improvement

        2. **Don't use meta-components when:**
           - Simple one-off tasks
           - Direct tool use is clearer
           - Overhead not justified

        3. **Store meta-patterns in:**
           - Layer: long_term
           - Intent: planning or analysis
           - Keywords: meta, pattern, creation
        """

        await self.memory.store(meta_knowledge, {
            "agent": "knowledge-base-populator",
            "category": "meta-components-documentation",
            "project": self.project,
            "intent": "documentation",
            "layer": "long_term",
            "timestamp": self.timestamp,
            "keywords": ["meta", "self-modifying", "meta-skills", "meta-agents", "meta-commands"]
        })

        print("  ✓ Stored meta-components knowledge\n")


    # ========== CLAUDE.MD KNOWLEDGE ==========

    async def populate_claude_md_knowledge(self):
        """Populate CLAUDE.md conventions and knowledge"""
        print("📋 Populating CLAUDE.md knowledge...")

        # Read the actual CLAUDE.md file
        claude_md_path = Path("C:/Users/17175/CLAUDE.md")
        if claude_md_path.exists():
            claude_md_content = claude_md_path.read_text(encoding='utf-8')
        else:
            claude_md_content = "CLAUDE.md file not found"

        claude_md_knowledge = f"""
        CLAUDE.MD - PROJECT INSTRUCTIONS AND CONVENTIONS

        Location: C:\\Users\\17175\\CLAUDE.md
        Purpose: Project-level instructions that override default behavior
        Scope: Global for all Claude Code sessions in this directory

        KEY CONVENTIONS FROM CLAUDE.MD:

        1. **CONCURRENT EXECUTION (CRITICAL)**
           - ALL operations MUST be concurrent/parallel in a single message
           - NEVER save working files, text/mds and tests to the root folder
           - ALWAYS organize files in appropriate subdirectories
           - USE CLAUDE CODE'S TASK TOOL for spawning agents concurrently

        2. **GOLDEN RULE: "1 MESSAGE = ALL RELATED OPERATIONS"**
           Mandatory Patterns:
           - TodoWrite: Batch ALL todos in ONE call (5-10+ todos minimum)
           - Task tool: Spawn ALL agents in ONE message with full instructions
           - File operations: Batch ALL reads/writes/edits in ONE message
           - Bash commands: Batch ALL terminal operations in ONE message
           - Memory operations: Batch ALL store/retrieve in ONE message

        3. **FILE ORGANIZATION**
           Never save to root folder. Use these directories:
           - /src - Source code files
           - /tests - Test files
           - /docs - Documentation and markdown files
           - /config - Configuration files
           - /scripts - Utility scripts
           - /examples - Example code

        4. **SPARC METHODOLOGY**
           Five phases:
           - Specification: Requirements analysis
           - Pseudocode: Algorithm design
           - Architecture: System design
           - Refinement: TDD implementation
           - Completion: Integration

        5. **AGENT EXECUTION FLOW**
           Correct Pattern:
           1. Optional: MCP tools set up coordination topology
           2. Required: Task tool spawns agents that do actual work
           3. Required: Each agent runs hooks for coordination
           4. Required: Batch all operations in single messages

        6. **AGENT COORDINATION PROTOCOL**
           Every Agent MUST:
           BEFORE Work:
           - npx claude-flow@alpha hooks pre-task --description "[task]"
           - npx claude-flow@alpha hooks session-restore --session-id "swarm-[id]"

           DURING Work:
           - npx claude-flow@alpha hooks post-edit --file "[file]"
           - npx claude-flow@alpha hooks notify --message "[what was done]"

           AFTER Work:
           - npx claude-flow@alpha hooks post-task --task-id "[task]"
           - npx claude-flow@alpha hooks session-end --export-metrics true

        7. **TOOLS AND MCPS**
           Claude Code Handles ALL EXECUTION:
           - Task tool: Spawn and run agents concurrently
           - File operations (Read, Write, Edit, Glob, Grep)
           - Code generation and programming
           - Bash commands and system operations
           - TodoWrite and task management

           MCP Tools ONLY COORDINATE:
           - Swarm initialization (topology setup)
           - Agent type definitions (coordination patterns)
           - Task orchestration (high-level planning)
           - Memory management

        8. **MCP SERVERS INSTALLED**
           Required: Claude Flow (foundation)
           - npm install -g claude-flow@alpha
           - claude mcp add claude-flow npx claude-flow@alpha mcp start

           Recommended: Advanced features
           - npm install -g ruv-swarm flow-nexus@latest
           - claude mcp add ruv-swarm npx ruv-swarm mcp start
           - claude mcp add flow-nexus npx flow-nexus@latest mcp start

           Production: Code quality & memory
           - connascence-analyzer (code quality)
           - memory-mcp (persistent memory)
           - focused-changes (change tracking)
           - ToC (documentation)

        9. **PERFORMANCE BENEFITS**
           - 84.8% SWE-Bench solve rate
           - 32.3% token reduction
           - 2.8-4.4x speed improvement
           - 27+ neural models

        10. **HOOKS INTEGRATION**
            Pre-Operation:
            - Auto-assign agents by file type
            - Validate commands for safety
            - Prepare resources automatically

            Post-Operation:
            - Auto-format code
            - Train neural patterns
            - Update memory

            Session Management:
            - Generate summaries
            - Persist state
            - Track metrics

        FULL CLAUDE.MD CONTENT:

        {claude_md_content}

        ENFORCEMENT:
        - These instructions OVERRIDE any default behavior
        - MUST be followed exactly as written
        - Applies to all Claude Code sessions
        - Can be extended via @CLAUDE.md imports
        """

        await self.memory.store(claude_md_knowledge, {
            "agent": "knowledge-base-populator",
            "category": "claude-md-documentation",
            "project": self.project,
            "intent": "documentation",
            "layer": "long_term",
            "timestamp": self.timestamp,
            "keywords": ["claude-md", "conventions", "rules", "sparc", "concurrent", "execution"]
        })

        print("  ✓ Stored CLAUDE.md knowledge\n")


    # ========== INTEGRATION PATTERNS KNOWLEDGE ==========

    async def populate_integration_patterns(self):
        """Populate integration patterns and workflows"""
        print("🔗 Populating Integration Patterns knowledge...")

        integration_knowledge = """
        INTEGRATION PATTERNS AND WORKFLOWS

        This document describes common integration patterns between all components:
        MCP servers, agents, skills, memory, and hooks.

        PATTERN 1: FULL-STACK FEATURE DEVELOPMENT

        Scenario: Implement authentication system with database, API, and UI

        Components:
        - MCP: memory-mcp, connascence-analyzer, focused-changes, sequential-thinking, git
        - Agents: researcher, architect, backend-dev, coder, tester, reviewer
        - Skills: feature-dev-complete, code-review-assistant, functionality-audit

        Workflow:
        1. Planning (researcher + sequential-thinking + memory-mcp):
           - Research auth best practices
           - Store findings in memory (intent='research')
           - Use sequential-thinking for problem decomposition

        2. Architecture (architect + ToC + memory-mcp):
           - Design system architecture
           - Generate TOC for docs
           - Store architecture in memory (sparc_phase='architecture')

        3. Implementation (backend-dev + coder):
           - backend-dev: Database schema + API endpoints
           - coder: UI components
           - Both use: connascence-analyzer + focused-changes + memory-mcp
           - Store: Implementation decisions in memory

        4. Testing (tester + playwright + focused-changes):
           - Unit tests with focused-changes tracking
           - Integration tests with playwright
           - Root cause analysis if failures
           - Store: Test patterns in memory

        5. Review (reviewer + connascence-analyzer + git):
           - Quality check with connascence-analyzer
           - Git history review
           - Store: Review findings in memory

        6. Integration (all agents + hooks):
           - Hooks auto-format code
           - Hooks update memory
           - Hooks export metrics

        PATTERN 2: CODE QUALITY WORKFLOW

        Scenario: Ensure zero violations before commit

        Components:
        - MCP: connascence-analyzer, focused-changes, memory-mcp
        - Agents: coder, reviewer
        - Skills: functionality-audit, theater-detection-audit

        Workflow:
        1. Start: focused-changes.start_tracking(file, content)
        2. Code: Write implementation
        3. Analyze: connascence-analyzer.analyze_file(file, 'full')
        4. Fix: Address all violations
        5. Verify: Re-analyze until 0 violations
        6. Check scope: focused-changes.analyze_changes(new_content)
        7. Store: memory-mcp.memory_store(patterns, {intent: 'analysis'})
        8. Audit: Run functionality-audit + theater-detection-audit
        9. Commit: Only if all checks pass

        PATTERN 3: SWARM COORDINATION

        Scenario: Parallel task execution with coordination

        Components:
        - MCP: ruv-swarm, claude-flow, memory-mcp
        - Agents: Multiple specialized agents
        - Skills: Custom coordination skill

        Workflow:
        1. Initialize: ruv-swarm.swarm_init({topology: 'mesh', maxAgents: 5})
        2. Spawn: Task tool spawns agents concurrently in single message
        3. Coordinate: Agents use memory-mcp for shared state
        4. Hooks: Pre-task and post-task hooks for each agent
        5. Memory: All agents store to memory with consistent tagging
        6. Sync: Hooks ensure memory synchronization
        7. Complete: Final synthesis by coordinator agent

        PATTERN 4: MEMORY-DRIVEN DEVELOPMENT

        Scenario: Learn from past implementations

        Components:
        - MCP: memory-mcp
        - Agents: All agents
        - Skills: All skills

        Workflow:
        1. Query: memory-mcp.vector_search("similar implementation")
        2. Learn: Review past patterns and decisions
        3. Adapt: Apply learned patterns to current task
        4. Implement: With knowledge from memory
        5. Store: New patterns back to memory
        6. Tag: Proper WHO/WHEN/PROJECT/WHY tagging
        7. Layer: Choose appropriate retention layer

        PATTERN 5: META-LEVEL COMPONENT CREATION

        Scenario: Create new skill for specific workflow

        Components:
        - MCP: memory-mcp, ToC
        - Meta-Skills: skill-builder, agent-creator
        - Agents: system-architect

        Workflow:
        1. Analyze: intent-analyzer determines need
        2. Research: memory-mcp.vector_search("similar skills")
        3. Design: system-architect designs skill structure
        4. Create: skill-builder generates skill file
        5. Validate: functionality-audit verifies skill works
        6. Store: memory-mcp stores creation pattern
        7. Use: New skill immediately available

        PATTERN 6: SPARC METHODOLOGY END-TO-END

        Scenario: Complete feature from requirements to deployment

        Components:
        - MCP: All MCP servers
        - Agents: SPARC agents (specification, pseudocode, architecture, refinement, sparc-coder)
        - Skills: sparc-methodology, feature-dev-complete
        - Command: /sparc

        Workflow:
        1. Specification (specification agent + sequential-thinking + memory-mcp):
           - Gather requirements
           - Break down with sequential-thinking
           - Store in memory (sparc_phase='specification', layer='long_term')

        2. Pseudocode (pseudocode agent + ToC + memory-mcp):
           - Design algorithms
           - Create pseudocode
           - Store in memory (sparc_phase='pseudocode', layer='mid_term')

        3. Architecture (architecture agent + ToC + memory-mcp):
           - Design system architecture
           - Create documentation structure
           - Store in memory (sparc_phase='architecture', layer='long_term')

        4. Refinement (refinement agent + connascence-analyzer + memory-mcp):
           - TDD implementation
           - Quality validation
           - Store in memory (sparc_phase='refinement', layer='mid_term')

        5. Code (sparc-coder + all code quality tools):
           - Implementation with coder, connascence-analyzer, focused-changes
           - Continuous quality checking
           - Store final implementation in memory

        PATTERN 7: DOCUMENTATION GENERATION

        Scenario: Generate comprehensive API documentation

        Components:
        - MCP: ToC, markitdown, memory-mcp
        - Agents: api-docs
        - Skills: Custom documentation skill

        Workflow:
        1. Structure: ToC.generate_toc(codebase)
        2. Extract: Get docstrings and type hints
        3. Convert: markitdown for existing docs
        4. Generate: OpenAPI/Swagger specs
        5. Store: memory-mcp stores documentation patterns
        6. Output: Complete API documentation

        PATTERN 8: TEST-DRIVEN DEVELOPMENT

        Scenario: TDD workflow with automatic testing

        Components:
        - MCP: playwright, focused-changes, connascence-analyzer, memory-mcp
        - Agents: tester, coder
        - Skills: tdd-london-swarm

        Workflow:
        1. Write test: tester creates failing test
        2. Track: focused-changes.start_tracking(test_file)
        3. Run: Execute test (should fail)
        4. Implement: coder writes minimal code to pass
        5. Test: playwright runs automated tests
        6. Refactor: connascence-analyzer guides improvements
        7. Verify: focused-changes ensures changes stayed focused
        8. Store: memory-mcp stores TDD patterns

        PATTERN 9: CONTINUOUS INTEGRATION

        Scenario: GitHub Actions workflow with quality gates

        Components:
        - MCP: git, connascence-analyzer, playwright, memory-mcp
        - Agents: cicd-engineer, reviewer
        - Skills: workflow-automation

        Workflow:
        1. Commit: git tracks all changes
        2. Pre-commit: connascence-analyzer runs analysis
        3. Tests: playwright runs automated tests
        4. Quality: Verify 0 violations
        5. Push: Only if all gates pass
        6. Store: memory-mcp stores CI/CD patterns
        7. Learn: Future runs use stored patterns

        PATTERN 10: CROSS-SESSION MEMORY

        Scenario: Resume work after days/weeks

        Components:
        - MCP: memory-mcp
        - All agents
        - Hooks: session-start, session-end

        Workflow:
        1. Session End:
           - hooks session-end exports state
           - memory-mcp stores session summary
           - Tag with timestamp, project

        2. Session Start:
           - hooks session-start restores context
           - memory-mcp.vector_search("recent work on [project]")
           - Load relevant patterns and decisions

        3. Continue:
           - All context restored
           - Work continues seamlessly
           - New knowledge added to memory

        KEY INTEGRATION PRINCIPLES:

        1. **Always Use Memory**: Store all important decisions, patterns, results
        2. **Tag Consistently**: Use WHO/WHEN/PROJECT/WHY for all memory operations
        3. **Batch Operations**: All related operations in single message
        4. **Quality First**: Run connascence-analyzer before commits
        5. **Track Changes**: Use focused-changes for scope control
        6. **Learn Patterns**: Store successful patterns for future use
        7. **Coordinate via Hooks**: Let hooks handle automation
        8. **Document with ToC**: Generate documentation structure automatically
        9. **Test with Playwright**: Automate browser testing
        10. **Version with Git**: Track all changes in git

        ANTI-PATTERNS TO AVOID:

        1. ❌ Sequential messages instead of batched operations
        2. ❌ Saving files to root directory
        3. ❌ Skipping connascence-analyzer before commits
        4. ❌ Forgetting memory tagging metadata
        5. ❌ Not using focused-changes for scope control
        6. ❌ Storing in wrong memory layer
        7. ❌ Missing WHO/WHEN/PROJECT/WHY tags
        8. ❌ Using MCP tools for execution (use Task tool)
        9. ❌ Ignoring hooks automation opportunities
        10. ❌ Not learning from stored patterns
        """

        await self.memory.store(integration_knowledge, {
            "agent": "knowledge-base-populator",
            "category": "integration-patterns-documentation",
            "project": self.project,
            "intent": "documentation",
            "layer": "long_term",
            "timestamp": self.timestamp,
            "keywords": ["integration", "patterns", "workflows", "best-practices", "anti-patterns"]
        })

        print("  ✓ Stored integration patterns knowledge\n")


async def main():
    """Main entry point"""
    populator = KnowledgeBasePopulator()
    await populator.populate_all()


if __name__ == "__main__":
    asyncio.run(main())
