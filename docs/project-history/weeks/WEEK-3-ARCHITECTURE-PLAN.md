# Week 3 Architecture Plan: Curation UI

**Project**: Memory MCP Triple System v5.0
**Date**: 2025-10-18
**Week**: 3 of 8 (Curation UI Implementation)
**Methodology**: SPARC - Architecture Phase

---

## Executive Summary

### Objective

Create a **simple, fast curation interface** (<5 min/day workflow) for managing Obsidian vault memory chunks with lifecycle tagging and verification flags.

### Design Principles

1. **Simplicity First**: Flask templates (no React complexity for Week 3)
2. **<5 min/day**: Single-page workflow, batch operations
3. **Lightweight**: Reuse existing cache layer, minimal DB overhead
4. **NASA Rule 10**: All functions ≤60 LOC

### Architecture Decision: Flask vs React

**Decision**: **Flask with Jinja2 templates** ✅

**Rationale**:
- Week 3 budget: 3 days (Flask = 2 days, React = 4-5 days)
- Single-user use case (no real-time collaboration)
- Reuse existing FastAPI/Flask patterns from MCP server
- Can upgrade to React in Phase 2 if needed

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Curation UI (Week 3)                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Flask Server │→ │ Jinja2 Tmpls │→ │   Browser    │  │
│  │ (curation    │  │ (HTML/CSS)   │  │  (User)      │  │
│  │  routes)     │  └──────────────┘  └──────────────┘  │
│  └──────┬───────┘                                       │
│         │                                                │
│         ↓                                                │
│  ┌──────────────────────────────────────────┐           │
│  │     Curation Service (Business Logic)    │           │
│  ├──────────────────────────────────────────┤           │
│  │ • Lifecycle Tagging                      │           │
│  │ • Verification Flags                     │           │
│  │ • Time Tracking                          │           │
│  │ • User Preferences                       │           │
│  └──────┬───────────────────────────────────┘           │
│         │                                                │
│         ↓                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ ChromaDB     │  │ Memory Cache │  │  JSON Store  │  │
│  │ (metadata)   │  │ (preferences)│  │ (time logs)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User loads curation page** → Flask renders batch of 20 unverified chunks
2. **User tags lifecycle** (permanent/temporary/ephemeral) → Update ChromaDB metadata
3. **User marks verified** (✅) → Update ChromaDB metadata + time log
4. **Page auto-tracks time** → JavaScript timer → POST to /api/curation/time
5. **User saves preferences** → Cache layer (TTL 30 days)

---

## Component Specifications

### 1. Flask Server (`src/ui/curation_app.py`)

**Purpose**: Web server for curation interface

**Routes**:

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Home page (redirect to /curate) |
| `/curate` | GET | Curation interface (batch of 20 chunks) |
| `/api/curate/tag` | POST | Update lifecycle tag |
| `/api/curate/verify` | POST | Mark chunk as verified |
| `/api/curate/time` | POST | Log curation time |
| `/settings` | GET/POST | User preferences UI |
| `/api/settings` | GET/PUT | Preferences API |

**Dependencies**:
- Flask (web framework)
- Jinja2 (templating)
- CurationService (business logic)

**LOC Estimate**: ~120 LOC (routes + config)

---

### 2. Curation Service (`src/services/curation_service.py`)

**Purpose**: Business logic for curation operations

**Methods**:

```python
class CurationService:
    def get_unverified_chunks(limit: int = 20) -> List[Dict]
    def tag_lifecycle(chunk_id: str, lifecycle: str) -> bool
    def mark_verified(chunk_id: str) -> bool
    def log_time(session_id: str, duration_seconds: int) -> None
    def get_preferences(user_id: str = "default") -> Dict
    def save_preferences(user_id: str, preferences: Dict) -> None
```

**Storage**:
- **ChromaDB metadata**: Lifecycle tags, verification flags
- **Memory cache**: User preferences (TTL 30 days)
- **JSON file**: Time logs (`./data/curation_time.json`)

**LOC Estimate**: ~180 LOC (6 methods × 30 LOC each)

---

### 3. Jinja2 Templates

**Templates**:

1. **`base.html`** (30 LOC):
   - Common layout (header, nav, footer)
   - CSS/JS includes
   - Title block

2. **`curate.html`** (80 LOC):
   - Batch of 20 chunks (cards)
   - Lifecycle buttons (permanent/temporary/ephemeral)
   - Verify checkbox (✅)
   - Time tracker (JavaScript)
   - "Next batch" button

3. **`settings.html`** (50 LOC):
   - Time budget slider (5-30 min/day)
   - Auto-suggest toggle
   - Weekly review scheduler (day + time)
   - Save button

**Total Template LOC**: ~160 LOC

---

### 4. Data Models

#### Chunk Metadata (ChromaDB)

```python
{
    'id': 'uuid-1234',
    'text': 'Chunk text...',
    'file_path': '/vault/note.md',
    'chunk_index': 0,
    'lifecycle': 'temporary',       # NEW: permanent/temporary/ephemeral
    'verified': False,              # NEW: True/False
    'verified_at': '2025-10-18',    # NEW: ISO timestamp
    'created_at': '2025-10-15',
    'updated_at': '2025-10-18'
}
```

#### User Preferences (Memory Cache)

```python
{
    'user_id': 'default',
    'time_budget_minutes': 5,       # Daily curation budget
    'auto_suggest': True,           # Auto-suggest lifecycle tags
    'weekly_review_day': 'sunday',  # Day of week
    'weekly_review_time': '10:00',  # Time (24h format)
    'batch_size': 20,               # Chunks per batch
    'default_lifecycle': 'temporary' # Default tag
}
```

#### Time Log (JSON File)

```python
{
    'sessions': [
        {
            'session_id': 'uuid-5678',
            'date': '2025-10-18',
            'duration_seconds': 180,     # 3 minutes
            'chunks_curated': 12
        }
    ],
    'stats': {
        'total_time_minutes': 45,
        'avg_time_per_day': 4.2,
        'days_active': 7
    }
}
```

---

## Lifecycle Tag Semantics

### Tag Definitions

| Tag | Meaning | Retention | Use Case |
|-----|---------|-----------|----------|
| **permanent** | Long-term knowledge | Forever | Core concepts, reference material |
| **temporary** | Medium-term utility | 90 days | Project notes, todos |
| **ephemeral** | Short-term scratchpad | 7 days | Quick thoughts, drafts |

### Auto-Suggest Logic

```python
def auto_suggest_lifecycle(chunk: Dict) -> str:
    """
    Auto-suggest lifecycle tag based on heuristics.

    Rules:
    1. Contains "TODO" or "FIXME" → temporary
    2. Contains "Reference" or "Definition" → permanent
    3. <50 words → ephemeral
    4. >200 words → permanent
    5. Default → temporary
    """
    text = chunk['text'].lower()
    word_count = len(text.split())

    if 'todo' in text or 'fixme' in text:
        return 'temporary'
    if 'reference' in text or 'definition' in text:
        return 'permanent'
    if word_count < 50:
        return 'ephemeral'
    if word_count > 200:
        return 'permanent'

    return 'temporary'  # Default
```

---

## Verification Flag Workflow

### Two-Tier Verification

1. **Stage 1: Unverified** (⚠️):
   - All chunks start unverified
   - May contain hallucinations or outdated info
   - Show warning in search results

2. **Stage 2: Verified** (✅):
   - User manually confirms accuracy
   - High confidence for retrieval
   - Prioritized in search results

### Verification UI

**Curate Page** (`curate.html`):
```html
<div class="chunk-card">
  <p class="chunk-text">{{ chunk.text }}</p>

  <!-- Lifecycle buttons -->
  <div class="lifecycle-buttons">
    <button data-lifecycle="permanent">📌 Permanent</button>
    <button data-lifecycle="temporary">🕐 Temporary</button>
    <button data-lifecycle="ephemeral">💨 Ephemeral</button>
  </div>

  <!-- Verification checkbox -->
  <label>
    <input type="checkbox" class="verify-checkbox"
           data-chunk-id="{{ chunk.id }}">
    ✅ Verified
  </label>
</div>
```

---

## Time Tracking Implementation

### Client-Side Timer (JavaScript)

```javascript
// Track curation session time
let sessionStart = Date.now();
let chunksTagged = 0;

// On tag/verify
document.querySelectorAll('.lifecycle-button, .verify-checkbox').forEach(el => {
  el.addEventListener('click', () => {
    chunksTagged++;
  });
});

// On page unload, log time
window.addEventListener('beforeunload', () => {
  const duration = Math.floor((Date.now() - sessionStart) / 1000);

  fetch('/api/curate/time', {
    method: 'POST',
    body: JSON.stringify({
      session_id: generateUUID(),
      duration_seconds: duration,
      chunks_curated: chunksTagged
    }),
    keepalive: true  // Ensure POST completes
  });
});
```

### Server-Side Logging

```python
def log_time(session_id: str, duration_seconds: int, chunks_curated: int):
    """Log curation session time to JSON file."""
    log_file = Path('./data/curation_time.json')

    # Load existing log
    if log_file.exists():
        with open(log_file, 'r') as f:
            log = json.load(f)
    else:
        log = {'sessions': [], 'stats': {}}

    # Add session
    log['sessions'].append({
        'session_id': session_id,
        'date': datetime.now().isoformat(),
        'duration_seconds': duration_seconds,
        'chunks_curated': chunks_curated
    })

    # Update stats
    log['stats'] = calculate_stats(log['sessions'])

    # Save
    with open(log_file, 'w') as f:
        json.dump(log, f, indent=2)
```

---

## User Preferences Storage

### Cache Layer Integration

**Reuse existing `MemoryCache`** (from Week 2):

```python
from src.cache.memory_cache import MemoryCache

# Initialize preferences cache (30-day TTL)
preferences_cache = MemoryCache(
    ttl_seconds=30 * 24 * 3600,  # 30 days
    max_size=1000
)

def get_preferences(user_id: str = "default") -> Dict:
    """Get user preferences from cache."""
    prefs = preferences_cache.get(f"prefs:{user_id}")

    if prefs is None:
        # Default preferences
        prefs = {
            'user_id': user_id,
            'time_budget_minutes': 5,
            'auto_suggest': True,
            'weekly_review_day': 'sunday',
            'weekly_review_time': '10:00',
            'batch_size': 20,
            'default_lifecycle': 'temporary'
        }
        preferences_cache.set(f"prefs:{user_id}", prefs)

    return prefs

def save_preferences(user_id: str, prefs: Dict) -> None:
    """Save user preferences to cache."""
    preferences_cache.set(f"prefs:{user_id}", prefs)
```

---

## Testing Strategy

### Unit Tests (20 tests)

**Test Files**:

1. **`test_curation_service.py`** (12 tests):
   - `test_get_unverified_chunks`
   - `test_tag_lifecycle_valid`
   - `test_tag_lifecycle_invalid`
   - `test_mark_verified`
   - `test_log_time`
   - `test_calculate_stats`
   - `test_get_preferences_default`
   - `test_get_preferences_cached`
   - `test_save_preferences`
   - `test_auto_suggest_lifecycle_todo`
   - `test_auto_suggest_lifecycle_short`
   - `test_auto_suggest_lifecycle_long`

2. **`test_curation_app.py`** (8 tests):
   - `test_curate_route_get`
   - `test_tag_lifecycle_post`
   - `test_verify_chunk_post`
   - `test_log_time_post`
   - `test_settings_get`
   - `test_settings_post`
   - `test_preferences_api_get`
   - `test_preferences_api_put`

### Integration Tests (5 tests)

**Test File**: `test_curation_workflow.py`

1. `test_full_curation_workflow` - Load → Tag → Verify → Log
2. `test_batch_processing` - 20 chunks in <5 min
3. `test_preferences_persistence` - Save → Reload
4. `test_time_tracking_accuracy` - Timer accuracy ±5s
5. `test_auto_suggest_accuracy` - 80%+ correct suggestions

---

## Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Page load** | <500ms | Flask render + 20 chunks from ChromaDB |
| **Tag/Verify API** | <50ms | Metadata update in ChromaDB |
| **Batch processing** | <5 min | 20 chunks × 15 sec/chunk |
| **Memory usage** | <50MB | Flask + templates (lightweight) |

---

## File Structure (Week 3 Additions)

```
memory-mcp-triple-system/
├── src/
│   ├── ui/                           # NEW (Week 3)
│   │   ├── __init__.py              # NEW
│   │   ├── curation_app.py          # NEW (120 LOC) - Flask server
│   │   └── templates/               # NEW
│   │       ├── base.html            # NEW (30 LOC)
│   │       ├── curate.html          # NEW (80 LOC)
│   │       └── settings.html        # NEW (50 LOC)
│   ├── services/                     # NEW (Week 3)
│   │   ├── __init__.py              # NEW
│   │   └── curation_service.py      # NEW (180 LOC)
│   └── static/                       # NEW (Week 3)
│       ├── css/
│       │   └── main.css             # NEW (50 LOC)
│       └── js/
│           └── curation.js          # NEW (80 LOC)
├── tests/
│   └── unit/
│       ├── test_curation_service.py # NEW (12 tests)
│       └── test_curation_app.py     # NEW (8 tests)
├── tests/
│   └── integration/
│       └── test_curation_workflow.py # NEW (5 tests)
├── data/                             # NEW (Week 3)
│   └── curation_time.json           # NEW (time logs)
└── docs/
    └── WEEK-3-IMPLEMENTATION-SUMMARY.md # NEW
```

**Total New Files**: 14
**Total LOC Estimate**: ~610 LOC (code) + 160 LOC (templates) = 770 LOC

---

## Implementation Plan (3 Days)

### Day 1: Core Service Layer (6 hours)

1. **Morning** (3 hours):
   - Create `curation_service.py` (180 LOC)
   - Implement 6 methods (tag, verify, time, preferences)
   - Unit tests (12 tests)

2. **Afternoon** (3 hours):
   - Create Flask app skeleton (`curation_app.py`)
   - 7 routes (GET/POST handlers)
   - Unit tests (8 tests)

**Deliverables**: 300 LOC code + 20 tests passing

---

### Day 2: UI Templates & Frontend (6 hours)

1. **Morning** (3 hours):
   - Create Jinja2 templates (base, curate, settings)
   - Basic CSS styling (clean, minimal)
   - Lifecycle button styling

2. **Afternoon** (3 hours):
   - JavaScript time tracker
   - AJAX for tag/verify (no page reload)
   - Form validation

**Deliverables**: 160 LOC templates + 130 LOC CSS/JS

---

### Day 3: Integration & Testing (6 hours)

1. **Morning** (3 hours):
   - Integration tests (5 tests)
   - End-to-end workflow testing
   - Bug fixes

2. **Afternoon** (3 hours):
   - Performance optimization
   - Documentation (WEEK-3-IMPLEMENTATION-SUMMARY.md)
   - Demo preparation

**Deliverables**: 5 integration tests + documentation

---

## Success Criteria

### Functional Requirements ✅

- [ ] Curation UI loads batch of 20 unverified chunks
- [ ] Lifecycle tagging works (permanent/temporary/ephemeral)
- [ ] Verification checkbox updates ChromaDB metadata
- [ ] Time tracker logs session duration
- [ ] User preferences persist (cache layer)
- [ ] Settings page allows customization

### Performance Requirements ✅

- [ ] Page load <500ms
- [ ] Tag/Verify API <50ms
- [ ] Batch processing <5 min (20 chunks)
- [ ] Memory usage <50MB

### Quality Requirements ✅

- [ ] 25 tests passing (20 unit + 5 integration)
- [ ] NASA Rule 10 compliance (100%)
- [ ] Code coverage ≥85%
- [ ] Zero TypeScript/Python errors

---

## Risk Analysis

### Technical Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| ChromaDB metadata slow | P2 | Batch updates, indexing | MONITOR |
| Flask not scalable | P3 | Single-user OK, can migrate to FastAPI later | ACCEPT |
| JavaScript timer inaccurate | P2 | Server-side validation, ±5s tolerance | TEST |

### Schedule Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| UI takes >3 days | P2 | Use simple Flask templates (no React) | MITIGATED |
| Integration issues | P2 | Daily integration testing | PLANNED |

---

## Next Steps (Week 4)

After Week 3 completion:

1. **NetworkX Graph Setup** (2 days):
   - Graph indexer (`graph_indexer.py`)
   - Pickle persistence
   - Node/edge creation

2. **Entity Extraction** (2 days):
   - spaCy NER integration
   - Entity deduplication
   - Graph population

3. **Testing** (1 day):
   - 25 new tests (15 graph + 10 entity)

---

**Version**: 5.0
**Date**: 2025-10-18
**Status**: Architecture Plan Complete
**Next Action**: Begin Day 1 Implementation (Curation Service Layer)
**Estimated Completion**: 3 days (Week 3 of 8)
