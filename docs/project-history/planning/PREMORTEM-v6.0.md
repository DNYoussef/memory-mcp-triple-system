# Memory MCP Triple System - PREMORTEM v6.0

**Version**: 6.0 (Loop 1 Iteration 1)
**Date**: 2025-10-18
**Status**: Draft - Awaiting Review
**Methodology**: Pre-Mortem Risk Analysis (Imagine project failed, work backward)

---

## Executive Summary

**Scenario**: It is 2025-12-18 (8 weeks after Week 14 deadline). The Memory MCP Triple System project has **failed catastrophically**. We are conducting a post-mortem to understand what went wrong.

**Purpose**: By imagining failure scenarios NOW (before implementation), we can identify and mitigate risks BEFORE they materialize.

**Methodology**:
1. **Imagine Project Failed**: Work backward from catastrophic failure
2. **Identify Root Causes**: 12 failure scenarios ranked by probability × impact
3. **Calculate Risk Score**: Quantitative risk assessment (target: <1,000 total risk)
4. **Define Mitigation**: Specific actions to prevent each failure
5. **Estimate Residual Risk**: Post-mitigation risk score

**Decision Criteria**:
- **Total Risk Score <1,000**: GO (93% confidence)
- **Total Risk Score 1,000-1,500**: CONDITIONAL GO (requires risk reduction plan)
- **Total Risk Score >1,500**: NO-GO (too risky, redesign needed)

---

## Failure Scenario Analysis

### Scenario 1: Bayesian Network Complexity Explosion

**Failure Description**: Week 10 Bayesian RAG implementation fails because pgmpy inference takes >10s for 1000-node networks, making the system unusable.

**Root Cause**:
- Bayesian inference is NP-hard (exponential in network size)
- Belief propagation requires message passing across all edges
- 1000 nodes × 1000 nodes = 1M potential edges (too large)

**Impact**: **CRITICAL**
- Tier 3 (Bayesian RAG) completely unusable
- Falls back to Tier 1 (Vector) + Tier 2 (HippoRAG) only
- 3-tier architecture reduced to 2-tier (architectural failure)
- Week 10 delivery blocked, cascades to Weeks 11-14

**Probability**: **40%** (Medium-High)
- pgmpy is known to struggle with large networks
- No production benchmarks exist for 1000+ node networks
- Sparse graph optimization not guaranteed to work

**Risk Score**: **Probability × Impact**
- Impact: 10 (Critical, blocks delivery)
- Probability: 0.40
- **Score: 4.0 × 100 = 400 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Hard Network Size Limit**: Max 1000 nodes (prune low-frequency entities)
2. **Sparse Graph Only**: Skip edges with confidence <0.3 (reduces edge count 60%)
3. **Timeout Fallback**: 1s timeout → fall back to Vector + HippoRAG (graceful degradation)
4. **Pre-Week 10 Benchmarking**: Test pgmpy on 500/1000/2000 node networks (Week 9 spike)

**Secondary Mitigation** (if primary fails):
5. **Alternative Algorithm**: Use approximate inference (Gibbs sampling) instead of exact (variable elimination)
6. **Reduce Network Size**: Max 500 nodes (50% reduction)
7. **Skip Bayesian Tier**: Accept 2-tier architecture (Vector + HippoRAG only)

**Residual Risk**: **25%** (Low-Medium)
- **Mitigated Score: 0.25 × 10 × 100 = 250 points** (-150 from original 400)

**Acceptance Criteria for Mitigation Success**:
- ✅ Bayesian inference <1s for 1000-node network (95th percentile)
- ✅ Timeout fallback tested (automated test with 2000-node network)
- ✅ Graceful degradation: System still usable without Bayesian tier

---

### Scenario 2: Obsidian Sync Latency >2s

**Failure Description**: Week 7 Obsidian file watcher takes >5s to index large markdown files (>10k tokens), breaking the "real-time feel" promise.

**Root Cause**:
- spaCy NER is slow (100ms per 512 tokens)
- Embedding generation is slow (50ms per chunk)
- Large files (10k tokens) = 20 chunks × 50ms = 1s embeddings + 2s NER = 3s total

**Impact**: **MEDIUM**
- User saves Obsidian note, queries immediately → stale results (poor UX)
- Breaks "Memory is Architecture" principle (Principle 1) if users avoid Obsidian due to lag
- Curation workflow frustrating (save → wait 5s → verify indexed)

**Probability**: **30%** (Medium)
- Large files are common (technical docs, meeting notes)
- Embedding models are known bottleneck (sentence-transformers on CPU)
- spaCy NER scales linearly with text length

**Risk Score**:
- Impact: 6 (Medium, UX degradation)
- Probability: 0.30
- **Score: 0.30 × 6 × 100 = 180 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Debouncing**: Wait 500ms after last file change before indexing (prevent rapid re-indexing)
2. **Incremental Indexing**: Update single file, not full reindex (10x faster)
3. **Background Queue**: Async processing (user doesn't wait for indexing completion)
4. **Progress Indicator**: Show "Indexing..." notification in curation UI

**Secondary Mitigation** (if primary fails):
5. **Parallel Processing**: Multi-threaded embedding generation (4 cores → 4x speedup)
6. **GPU Acceleration**: Use CUDA for sentence-transformers (10x speedup if GPU available)
7. **Chunk Size Increase**: 512 → 1024 tokens per chunk (reduces chunk count 50%)

**Residual Risk**: **15%** (Low)
- **Mitigated Score: 0.15 × 6 × 100 = 90 points** (-90 from original 180)

**Acceptance Criteria**:
- ✅ 10k token file indexed in <2s (95th percentile)
- ✅ Background queue prevents UI blocking
- ✅ User sees progress indicator (async feedback)

---

### Scenario 3: Curation Time >35 Minutes/Week (Defeats Active Curation Principle)

**Failure Description**: Week 12 curation workflow requires >1 hour/week, causing users to abandon active curation and revert to passive accumulation (defeats Memory Wall Principle 6).

**Root Cause**:
- Smart suggestions only 60% accurate (not 70% target)
- Batch operations limited to 10 chunks (not 20+)
- Weekly review of 200 session chunks × 20 seconds each = 67 minutes

**Impact**: **HIGH**
- Users abandon active curation (system becomes passive accumulation)
- Memory quality degrades (noise accumulates)
- Defeats core architectural principle (Principle 6: Compression is Curation)
- User trust in system erodes ("too much work for too little value")

**Probability**: **35%** (Medium)
- Smart suggestions require ML training (accuracy uncertain)
- Users generate more session data than estimated (200 chunks/week assumed, could be 400)
- Curation fatigue is well-documented problem (from Memory Wall research)

**Risk Score**:
- Impact: 9 (High, defeats core principle)
- Probability: 0.35
- **Score: 0.35 × 9 × 100 = 315 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Improve Smart Suggestions**: Aim for 80% accuracy (not 70%) via better ML training
2. **Increase Batch Size**: Support 20+ chunks tagged at once (not 10)
3. **Auto-Archive Low-Confidence**: Chunks with confidence <0.3 auto-tagged for deletion
4. **Smart Defaults**: Default to "keep" unless user explicitly marks "delete"

**Secondary Mitigation** (if primary fails):
5. **Reduce Review Frequency**: Bi-weekly review instead of weekly (50% reduction)
6. **Sampling**: Review only top-10% most relevant chunks (skip low-engagement chunks)
7. **Gamification**: Show "memory health score" (motivates users to maintain curation)

**Residual Risk**: **20%** (Low-Medium)
- **Mitigated Score: 0.20 × 9 × 100 = 180 points** (-135 from original 315)

**Acceptance Criteria**:
- ✅ Weekly curation <35 minutes (10 user testing sessions, average time)
- ✅ Smart suggestions ≥80% accuracy (1000 chunks validation)
- ✅ User retention: ≥80% of users still curating after 4 weeks

---

### Scenario 4: MCP Protocol Breaking Changes

**Failure Description**: Week 7-14: MCP (Model Context Protocol) releases v2.0 with breaking API changes. ChatGPT, Claude, and Gemini update to v2.0, breaking our MCP server.

**Root Cause**:
- MCP is a new standard (unstable API)
- LLM vendors prioritize their own needs over backward compatibility
- We built against MCP v1.0 spec, v2.0 changes authentication/query format

**Impact**: **HIGH**
- All 3 LLM clients (ChatGPT, Claude, Gemini) stop working
- Breaks "Portable First-Class" principle (Principle 5)
- Users locked out of their memory (catastrophic UX failure)
- Emergency hotfix required (unplanned work, schedule slip)

**Probability**: **15%** (Low-Medium)
- MCP is still evolving (higher chance of breaking changes)
- Vendors have incentive to maintain backward compatibility (moderate risk)
- We can version our API (v1, v2) to mitigate partially

**Risk Score**:
- Impact: 9 (High, breaks all LLM clients)
- Probability: 0.15
- **Score: 0.15 × 9 × 100 = 135 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Version MCP Server API**: Support both v1.0 and v2.0 (backward compatible)
2. **Monitor MCP Spec Updates**: Monthly check for breaking changes (early warning)
3. **Fallback REST API**: Direct HTTP endpoints (no MCP dependency)
4. **Automated Tests**: Integration tests with all 3 LLM clients (catch breakage early)

**Secondary Mitigation** (if primary fails):
5. **Emergency Hotfix Plan**: Pre-written migration guide (MCP v1.0 → v2.0)
6. **Client-Side Proxy**: User runs local proxy to translate v1.0 ↔ v2.0
7. **Direct LLM Integration**: Skip MCP, use OpenAI/Anthropic/Google APIs directly

**Residual Risk**: **5%** (Very Low)
- **Mitigated Score: 0.05 × 9 × 100 = 45 points** (-90 from original 135)

**Acceptance Criteria**:
- ✅ MCP server supports v1.0 and v2.0 (backward compatible)
- ✅ Fallback REST API functional (tested with curl/Postman)
- ✅ Integration tests with all 3 clients passing weekly

---

### Scenario 5: Mode Detection Accuracy <85%

**Failure Description**: Week 13 mode detection (planning vs execution vs brainstorming) only achieves 65% accuracy, causing frequent misclassifications and poor UX.

**Root Cause**:
- Keyword-based detection is brittle ("all options" → planning, "exact value" → execution)
- Users phrase queries ambiguously ("What should I do about X?" → planning or brainstorming?)
- ML-based detection requires training data (we have none at Week 13)

**Impact**: **LOW**
- User queries return wrong top-K (planning returns 5 instead of 20)
- UX degradation, but user can explicitly override mode (`mode=planning`)
- Not a blocker (graceful degradation)

**Probability**: **25%** (Medium)
- Mode detection is a known hard problem (query intent classification)
- We have no training data for ML-based detection
- Rule-based fallback is brittle

**Risk Score**:
- Impact: 4 (Low, user can override)
- Probability: 0.25
- **Score: 0.25 × 4 × 100 = 100 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Explicit Mode Override**: Always allow `mode=` query parameter (user controls)
2. **Rule-Based Fallback**: Keyword detection as baseline (65% accuracy)
3. **User Feedback Loop**: Log misclassifications, retrain quarterly
4. **Smart Defaults**: Default to planning mode (recall-optimized, safer than precision-only)

**Secondary Mitigation** (if primary fails):
5. **Remove Auto-Detection**: Always require explicit `mode=` parameter (user responsibility)
6. **UI Mode Selector**: Curation UI has dropdown ("Planning | Execution | Brainstorming")

**Residual Risk**: **10%** (Very Low)
- **Mitigated Score: 0.10 × 4 × 100 = 40 points** (-60 from original 100)

**Acceptance Criteria**:
- ✅ Mode detection ≥85% accuracy (if achievable)
- ✅ Explicit mode override works 100% of time
- ✅ Default to planning mode (safer fallback)

---

### Scenario 6: Storage Growth Exceeds Estimates (Disk Full)

**Failure Description**: Week 12-14: Users run out of disk space. Estimated 35MB/1000 chunks, actual usage is 120MB/1000 chunks (3.4x higher).

**Root Cause**:
- ChromaDB embeddings larger than expected (384-dimensional vectors + metadata)
- Bayesian network serialization bloated (pgmpy JSON is verbose)
- RAPTOR summaries stored separately (not counted in estimate)

**Impact**: **MEDIUM**
- System crashes when disk full (catastrophic user experience)
- Data loss if ChromaDB cannot write new chunks
- Users forced to manually delete chunks (breaks passive UX)

**Probability**: **20%** (Low-Medium)
- Embeddings size is well-known (unlikely to exceed estimate)
- Bayesian network size is uncertain (pgmpy serialization untested)
- RAPTOR summaries likely add 20MB (not trivial)

**Risk Score**:
- Impact: 7 (Medium-High, system crashes)
- Probability: 0.20
- **Score: 0.20 × 7 × 100 = 140 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Storage Monitoring**: Alert at 80% disk usage (email notification)
2. **Auto-Cleanup**: Purge session memory after 7 days (SPEC v6.0 requirement)
3. **Compression**: gzip old Bayesian networks (50% reduction)
4. **Size Estimates**: Track actual usage (log per-chunk storage in Week 7-8)

**Secondary Mitigation** (if primary fails):
5. **External Storage**: Move ChromaDB to S3/cloud (unlimited disk)
6. **Selective Deletion**: Automatically delete lowest-confidence chunks (preserve high-value memory)
7. **User Warning**: Show "Disk 90% full, please curate" notification

**Residual Risk**: **10%** (Very Low)
- **Mitigated Score: 0.10 × 7 × 100 = 70 points** (-70 from original 140)

**Acceptance Criteria**:
- ✅ Storage monitoring alerts at 80% (email sent to user)
- ✅ Auto-cleanup purges session memory after 7 days
- ✅ Actual storage growth <50MB/1000 chunks (measured in Week 8)

---

### Scenario 7: GraphRAG Entity Consolidation <90% Accuracy

**Failure Description**: Week 8 entity deduplication only achieves 70% accuracy (target: 90%), causing duplicate entities in knowledge graph ("Tesla" and "Tesla Inc" remain separate).

**Root Cause**:
- String similarity (Levenshtein) misses semantic variants ("Apple" company vs "apple" fruit)
- Embedding similarity (cosine >0.90) threshold too high (misses "Tesla Motors" vs "Tesla")
- Leiden community detection groups unrelated entities

**Impact**: **LOW-MEDIUM**
- Knowledge graph has duplicates (reduces HippoRAG recall)
- User queries "Tesla" miss "Tesla Inc" results
- Not a blocker (HippoRAG still functional, just less accurate)

**Probability**: **30%** (Medium)
- Entity deduplication is a known hard problem (many edge cases)
- No training data for ML-based approach (rule-based fallback only)
- Threshold tuning requires manual experimentation

**Risk Score**:
- Impact: 5 (Low-Medium, reduces accuracy but not critical)
- Probability: 0.30
- **Score: 0.30 × 5 × 100 = 150 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Lower Embedding Threshold**: Cosine >0.85 (from 0.90) → catch more variants
2. **Manual Synonym List**: Pre-populate common synonyms (Tesla = Tesla Inc = Tesla Motors)
3. **User Feedback Loop**: Log missed duplicates, retrain quarterly
4. **Validation Dataset**: Create 1000-entity test set (measure accuracy before Week 8 ends)

**Secondary Mitigation** (if primary fails):
5. **Accept 80% Accuracy**: Lower target from 90% to 80% (still functional)
6. **Manual Curation**: User-tagged synonyms (add "synonym_of" tag in Obsidian)

**Residual Risk**: **15%** (Low)
- **Mitigated Score: 0.15 × 5 × 100 = 75 points** (-75 from original 150)

**Acceptance Criteria**:
- ✅ Entity consolidation ≥90% accuracy (1000-entity test set)
- ✅ Manual synonym list covers top 100 entities (Tesla, Apple, Microsoft, etc.)
- ✅ User feedback loop functional (log missed duplicates)

---

### Scenario 8: Verification Stage False Positive Rate >2%

**Failure Description**: Week 14 two-stage verification marks 5% of correct facts as "unverified" (target: <2% false positive rate), causing user distrust.

**Root Cause**:
- Ground truth database incomplete (only 100 facts, users have 1000+ facts)
- String matching too strict (exact match only, misses paraphrases)
- Semantic similarity threshold too high (cosine >0.98 misses valid paraphrases)

**Impact**: **MEDIUM**
- Users see "unverified" warnings on correct facts (false alarms)
- User trust in system erodes ("Why does it think this is wrong?")
- Curation workflow disrupted (users manually verify false positives)

**Probability**: **25%** (Medium)
- Ground truth database requires manual curation (time-consuming)
- Paraphrasing detection is hard (many valid ways to state a fact)
- Threshold tuning requires experimentation

**Risk Score**:
- Impact: 6 (Medium, erodes user trust)
- Probability: 0.25
- **Score: 0.25 × 6 × 100 = 150 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Lower Similarity Threshold**: Cosine >0.95 (from 0.98) → catch paraphrases
2. **Expand Ground Truth**: Seed with 500 common facts (NASA rules, project policies)
3. **User Feedback**: "Mark as correct" button → add to ground truth
4. **Paraphrase Detection**: Use semantic similarity instead of exact string match

**Secondary Mitigation** (if primary fails):
5. **Accept 3-5% False Positive Rate**: Lower target from 2% to 5% (still useful)
6. **Optional Verification**: User can disable verification for brainstorming mode

**Residual Risk**: **15%** (Low)
- **Mitigated Score: 0.15 × 6 × 100 = 90 points** (-60 from original 150)

**Acceptance Criteria**:
- ✅ False positive rate <2% (validated on 1000-fact test set)
- ✅ Ground truth database has ≥500 facts (seeded before Week 14)
- ✅ User feedback loop functional ("Mark as correct" button works)

---

### Scenario 9: RAPTOR Clustering Quality Poor (Low BIC Score)

**Failure Description**: Week 9 RAPTOR hierarchical clustering produces low-quality clusters (BIC score indicates random groupings, not semantic clusters).

**Root Cause**:
- Recursive summarization loses key details (100 chunks → 10 summaries loses context)
- Clustering algorithm (K-Means) converges to local minimum (not global optimum)
- BIC metric is noisy (small changes in clusters cause large BIC swings)

**Impact**: **LOW**
- RAPTOR multi-level retrieval less accurate (queries at summary level return wrong results)
- Not a blocker (queries at chunk level still work)
- Tier 2 (HippoRAG) still functional (RAPTOR is enhancement, not core)

**Probability**: **20%** (Low-Medium)
- Clustering quality depends on data (uncertain until Week 9 testing)
- Recursive summarization is lossy by design (some information loss expected)
- BIC metric may not be ideal validation (consider alternatives)

**Risk Score**:
- Impact: 4 (Low, not critical path)
- Probability: 0.20
- **Score: 0.20 × 4 × 100 = 80 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Alternative Clustering**: Try HDBSCAN instead of K-Means (density-based)
2. **Validation Dataset**: Create 1000-chunk test set (measure cluster quality)
3. **Summarization Quality**: Use better summarization prompt (preserve key entities)
4. **BIC Alternatives**: Try Silhouette Score or Davies-Bouldin Index

**Secondary Mitigation** (if primary fails):
5. **Skip RAPTOR**: Accept 2-level hierarchy (chunks → summaries only, no abstracts)
6. **Manual Clustering**: User-defined tags as cluster labels (Obsidian frontmatter tags)

**Residual Risk**: **10%** (Very Low)
- **Mitigated Score: 0.10 × 4 × 100 = 40 points** (-40 from original 80)

**Acceptance Criteria**:
- ✅ BIC score indicates good clusters (lower = better, benchmark against random baseline)
- ✅ Multi-level retrieval returns relevant results at all 3 levels (chunk/summary/abstract)
- ✅ User testing: ≥70% of users find summary-level queries useful

---

### Scenario 10: Nexus Processor Overhead >100ms

**Failure Description**: Week 11 Nexus Processor 5-step pipeline takes 250ms (target: <100ms), adding unacceptable latency to end-to-end queries.

**Root Cause**:
- Deduplication step is slow (pairwise cosine similarity for 50 candidates = 1,225 comparisons)
- Ranking step requires sorting (50 candidates × 3 tiers = 150 scores)
- Filter step iterates over all candidates (no early termination)

**Impact**: **LOW**
- Query latency increases from 1s to 1.15s (15% degradation)
- Still within <1s 95th percentile target (most queries <1s)
- Not a blocker (acceptable performance degradation)

**Probability**: **20%** (Low-Medium)
- 5-step pipeline is algorithmically simple (low complexity)
- Deduplication is known bottleneck (pairwise comparisons are O(n²))
- Profiling will likely identify hotspot

**Risk Score**:
- Impact: 3 (Low, acceptable degradation)
- Probability: 0.20
- **Score: 0.20 × 3 × 100 = 60 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Optimize Deduplication**: Use approximate nearest neighbors (FAISS) instead of pairwise
2. **Parallel Ranking**: Multi-threaded sorting (4 cores → 4x speedup)
3. **Early Termination**: Stop filtering after top-K candidates (not all 50)
4. **Profiling**: Measure each step latency (identify bottleneck)

**Secondary Mitigation** (if primary fails):
5. **Increase Latency Target**: Accept <150ms Nexus overhead (total <1.15s)
6. **Skip Deduplication**: Accept duplicates in results (user filters manually)

**Residual Risk**: **10%** (Very Low)
- **Mitigated Score: 0.10 × 3 × 100 = 30 points** (-30 from original 60)

**Acceptance Criteria**:
- ✅ Nexus Processor overhead <100ms (95th percentile)
- ✅ Profiling identifies bottleneck (before Week 11 ends)
- ✅ Optimization applied (FAISS or parallel ranking)

---

### Scenario 11: Setup Time >15 Minutes (Adoption Barrier)

**Failure Description**: Week 7-14: New users take >30 minutes to set up the system (target: <15 minutes), causing abandonment.

**Root Cause**:
- spaCy model download takes 10 minutes (large file, slow connection)
- Obsidian vault setup requires manual configuration (find vault path, edit config)
- MCP server configuration complex (API keys, YAML editing)

**Impact**: **LOW-MEDIUM**
- User adoption lower than expected (40% abandonment vs 20% target)
- GitHub stars/community engagement lower
- Not a technical blocker (system works once set up)

**Probability**: **25%** (Medium)
- Setup complexity is known barrier (documented in user research)
- spaCy model download time varies by connection speed (unpredictable)
- Configuration complexity is subjective (some users find YAML editing easy)

**Risk Score**:
- Impact: 5 (Low-Medium, reduces adoption but not critical)
- Probability: 0.25
- **Score: 0.25 × 5 × 100 = 125 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **One-Command Install**: `pip install memory-mcp-system` bundles dependencies
2. **Pre-Download spaCy Model**: Include in Docker image (optional Dockerfile)
3. **Setup Wizard**: Interactive CLI prompts for vault path, API keys
4. **Video Tutorial**: YouTube walkthrough (<5 minutes)

**Secondary Mitigation** (if primary fails):
5. **Cloud Deployment**: One-click deploy to DigitalOcean (skip local setup)
6. **Simplified Config**: Minimal YAML (only vault_path required)

**Residual Risk**: **10%** (Very Low)
- **Mitigated Score: 0.10 × 5 × 100 = 50 points** (-75 from original 125)

**Acceptance Criteria**:
- ✅ Setup time <15 minutes (10 user testing sessions, average time)
- ✅ One-command install works (documented in README)
- ✅ Video tutorial published (YouTube, <5 minutes)

---

### Scenario 12: Memory Forgetting Deletes Important Chunks

**Failure Description**: Week 12 memory decay formula accidentally deletes high-value chunks because they're >30 days old (false negatives).

**Root Cause**:
- Decay formula too aggressive (`score = base_score * exp(-0.05 * days_old)`)
- Important chunks not tagged `priority: high` (user forgot to tag)
- Auto-cleanup purges without confirmation (no user review)

**Impact**: **MEDIUM**
- Users lose important personal memory (catastrophic data loss)
- User trust in system destroyed ("It deleted my preference!")
- Lawsuits possible if business-critical data lost

**Probability**: **15%** (Low-Medium)
- Decay formula is conservative (-0.05 decay rate is slow)
- Important chunks should be tagged (user responsibility, but mistakes happen)
- Auto-cleanup has safeguards (only session lifecycle, not personal)

**Risk Score**:
- Impact: 8 (High, data loss)
- Probability: 0.15
- **Score: 0.15 × 8 × 100 = 120 points**

**Mitigation Strategy**:

**Primary Mitigation**:
1. **Exempt Important Chunks**: `priority: high` immune to decay (hard-coded rule)
2. **Personal Lifecycle Exempt**: Never auto-delete `lifecycle: personal` (only session/project)
3. **User Review Before Deletion**: Weekly email summary ("These chunks will be deleted, review?")
4. **Undo Window**: 7-day trash bin before permanent deletion

**Secondary Mitigation** (if primary fails):
5. **Disable Auto-Cleanup**: User must manually delete (no automation)
6. **Backup System**: Daily snapshots of ChromaDB (restore if accidental deletion)

**Residual Risk**: **5%** (Very Low)
- **Mitigated Score: 0.05 × 8 × 100 = 40 points** (-80 from original 120)

**Acceptance Criteria**:
- ✅ Personal lifecycle never auto-deleted (hard-coded safeguard)
- ✅ Important chunks (`priority: high`) immune to decay
- ✅ User review email sent before auto-cleanup (weekly summary)

---

## Risk Score Summary

| Scenario | Impact | Probability | Original Risk | Mitigation | Residual Risk |
|----------|--------|-------------|---------------|------------|---------------|
| 1. Bayesian Complexity | 10 | 40% | 400 | Hard limits, timeout | 250 |
| 2. Obsidian Sync Latency | 6 | 30% | 180 | Debouncing, async | 90 |
| 3. Curation Time >35min | 9 | 35% | 315 | Smart suggestions, batch | 180 |
| 4. MCP Breaking Changes | 9 | 15% | 135 | Versioning, fallback | 45 |
| 5. Mode Detection <85% | 4 | 25% | 100 | Override, fallback | 40 |
| 6. Storage Growth | 7 | 20% | 140 | Monitoring, cleanup | 70 |
| 7. Entity Consolidation | 5 | 30% | 150 | Lower threshold, manual | 75 |
| 8. Verification FP >2% | 6 | 25% | 150 | Lower threshold, feedback | 90 |
| 9. RAPTOR Clustering | 4 | 20% | 80 | Alternative algorithms | 40 |
| 10. Nexus Overhead >100ms | 3 | 20% | 60 | Optimize, parallel | 30 |
| 11. Setup Time >15min | 5 | 25% | 125 | One-command, wizard | 50 |
| 12. Forgetting Deletes | 8 | 15% | 120 | Exempt important, review | 40 |
| **TOTAL** | - | - | **1,955** | **All Mitigated** | **1,000** |

---

## Decision: CONDITIONAL GO (94% Confidence)

### Risk Assessment

**Original Total Risk**: 1,955 points (HIGH RISK - above 1,500 threshold)
**Mitigated Total Risk**: 1,000 points (MODERATE RISK - at threshold boundary)

**Risk Reduction**: 1,955 → 1,000 = **48.8% reduction** via mitigation strategies

### GO/NO-GO Criteria

**Decision Matrix**:
- **Total Risk <1,000**: GO (93% confidence) ← **WE ARE HERE** (exactly at boundary)
- **Total Risk 1,000-1,500**: CONDITIONAL GO (requires risk reduction plan)
- **Total Risk >1,500**: NO-GO (too risky, redesign needed)

**Recommendation**: **CONDITIONAL GO with Mandatory Risk Reduction Plan**

### Conditions for GO

**Mandatory Actions Before Week 7 Implementation**:

1. **Week 9 Spike: Bayesian Network Benchmarking** (Risk #1, 250 residual risk)
   - Test pgmpy on 500/1000/2000 node networks
   - Validate 1s timeout works
   - If >1s, reduce max nodes to 500 or skip Bayesian tier

2. **Week 7 Spike: Obsidian Sync Performance Testing** (Risk #2, 90 residual risk)
   - Test 10k token file indexing latency
   - Validate debouncing prevents rapid re-indexing
   - If >2s, implement GPU acceleration or parallel processing

3. **Week 11-12: Curation UX User Testing** (Risk #3, 180 residual risk)
   - Recruit 10 alpha testers for Week 12 curation workflow
   - Measure actual curation time (target: <35 minutes)
   - If >35 minutes, reduce review frequency to bi-weekly

4. **Week 7: MCP Server Versioning** (Risk #4, 45 residual risk)
   - Implement v1.0/v2.0 backward compatibility BEFORE any LLM integration
   - Document fallback REST API
   - Automated tests with all 3 LLM clients

**Confidence Level**: 94% (high confidence with conditions met)

**Risk Tolerance**: Moderate (residual risk = 1,000 points, acceptable with contingencies)

---

## Iteration 2 (v6.1) Focus Areas

Based on PREMORTEM v6.0 analysis, **Iteration 2 (v6.1)** will refine:

1. **Bayesian Network Complexity** (250 residual risk)
   - Add Week 9 spike: Benchmark pgmpy (500/1000/2000 nodes)
   - Decision tree: If >1s, reduce to 500 nodes OR skip Bayesian tier

2. **Curation Time Target** (180 residual risk)
   - Increase smart suggestion target from 70% to 80% accuracy
   - Increase batch size from 10 to 20+ chunks
   - Add auto-archive for confidence <0.3 chunks

3. **Obsidian Sync Optimization** (90 residual risk)
   - Add GPU acceleration option (10x speedup if available)
   - Add parallel processing (multi-threaded embedding generation)

**Expected Risk Reduction (v6.1)**: 1,000 → 850 points (15% further reduction)

---

## Version History

**v6.0 (2025-10-18)**: Initial Loop 1 Iteration 1 pre-mortem
- Identified 12 failure scenarios
- Calculated risk scores (1,955 original, 1,000 mitigated)
- Recommended CONDITIONAL GO (94% confidence)
- Defined mandatory actions before Week 7 implementation

**Next Iteration (v6.1)**: Risk mitigation refinement
- Address top 3 residual risks (Bayesian, Curation, Obsidian)
- Target: 1,000 → 850 points (15% reduction)
- Increase confidence to 96%

---

**Receipt**:
- **Run ID**: loop1-iter1-premortem-v6.0
- **Timestamp**: 2025-10-18T19:45:00Z
- **Agent**: Strategic Planning (Loop 1)
- **Inputs**: SPEC v6.0, PLAN v6.0, Memory Wall principles
- **Tools Used**: Write (1 file), TodoWrite (1 update)
- **Changes**: Created PREMORTEM-v6.0.md (12 risks, 1,000 mitigated score, CONDITIONAL GO)
- **Status**: Ready for Iteration 2 (v6.1) refinement
