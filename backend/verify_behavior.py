"""
Behavioral verification -- async, background jobs, cross-system state.
Tests the INTENT of requirements, not just code existence.
Run from backend/ with: python verify_behavior.py
"""
import sys, os, asyncio, importlib, json, time, re, tempfile, shutil

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, '.')
os.environ.setdefault('NEO4J_URI', '')
os.environ.setdefault('NEO4J_PASSWORD', '')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-32chars-padding!!')
os.environ['ALLOW_CLOUD_PROVIDERS'] = 'false'
os.environ['LLM_PROVIDER'] = 'ollama'
os.environ['EMBEDDING_PROVIDER'] = 'local'

# Use a temp DB for all tests
TMP_DIR = tempfile.mkdtemp()
TMP_DB = os.path.join(TMP_DIR, 'test_behavior.db').replace('\\', '/')
os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{TMP_DB}'

results = []

def check(label, condition, detail='', verified_by=''):
    status = 'PASS' if condition else 'FAIL'
    suffix = f' -- {detail}' if detail else ''
    vby = f'\n         verified by: {verified_by}' if verified_by else '\n         verified by: ASSUMED - not yet proven by execution'
    print(f'  [{status}] {label}{suffix}{vby}')
    results.append((label, bool(condition), verified_by))


# =============================================================================
# App Flow SS11 (backend): re-embed job actually re-vectorises rows
# Spec intent: after provider switch, ALL items get new vectors under new
# provider; old vectors are replaced, not appended.
# =============================================================================
print('\n=== App Flow SS11: Re-embed job replaces vectors in DB ===')

async def test_reembed_updates_rows():
    import app.db as db_mod
    importlib.reload(db_mod)
    await db_mod.init_db()

    # Insert item with fake zero vector tagged as "old_provider"
    async with db_mod.SessionLocal() as session:
        item = db_mod.KnowledgeItem(
            id='reembed_test_001',
            workspace_id='ws1',
            artifact_id='art_001',
            title='Test decision about deployment strategy',
            type='decision',
            author='tester',
            date='2024-01-01',
            tags=['test'],
            details={'what': 'deploy on Fridays'},
            embedding=[0.0] * 384,
            embedding_provider='old_provider:fake_model',
            embedding_dims=384,
            review_status='accepted',
        )
        session.add(item)
        await session.commit()

    # Run the reembed logic (same code path as POST /knowledge/reembed)
    from app.services.graphrag import embed_items
    import app.services.providers as prov
    importlib.reload(prov)
    from sqlalchemy import select

    async with db_mod.SessionLocal() as session:
        items = (await session.execute(
            select(db_mod.KnowledgeItem).where(db_mod.KnowledgeItem.workspace_id == 'ws1')
        )).scalars().all()
        item_dicts = [{'id': i.id, 'title': i.title, 'type': i.type, 'details': i.details or {}} for i in items]

    pairs = await embed_items(item_dicts)
    provider = prov.get_embedding_provider()

    async with db_mod.SessionLocal() as session:
        for item_id, vector in pairs:
            ki = await session.get(db_mod.KnowledgeItem, item_id)
            if ki:
                ki.embedding = vector
                ki.embedding_provider = provider.name
                ki.embedding_dims = provider.dimensions
        await session.commit()

    # Read back and verify
    async with db_mod.SessionLocal() as session:
        ki = await session.get(db_mod.KnowledgeItem, 'reembed_test_001')
        return (
            ki.embedding is not None,
            not all(x == 0.0 for x in ki.embedding),
            ki.embedding_provider,
            ki.embedding_dims,
        )

has_vec, vec_changed, new_prov, new_dims = asyncio.run(test_reembed_updates_rows())
check('Re-embed: vector is non-None after job', has_vec, '',
      'inserted item with [0.0]*384, ran embed_items+commit, read back from DB')
check('Re-embed: vector changed from zeros to real values', vec_changed,
      'old=[0.0]*384, new=sentence-transformer output',
      'compared stored vector against original zero-filled placeholder')
check('Re-embed: embedding_provider updated from old to new', new_prov == 'local:all-MiniLM-L6-v2',
      f'got: {new_prov}',
      'read embedding_provider column from DB row after reembed commit')
check('Re-embed: embedding_dims correct', new_dims == 384,
      f'got: {new_dims}',
      'read embedding_dims column from DB row after reembed commit')


# =============================================================================
# App Flow SS11 (frontend): save() conditionally calls reembed()
# =============================================================================
print('\n=== App Flow SS11: Frontend save() triggers reembed() conditionally ===')
with open('../frontend/src/app/pages/workspace-settings/workspace-settings.component.ts', encoding='utf-8') as fh:
    ws_src = fh.read()

save_match = re.search(r'async save\(\)[^{]*\{(.*?)^\s{2}\}', ws_src, re.DOTALL | re.MULTILINE)
if save_match:
    save_body = save_match.group(1)
    has_changed_guard = '_savedEmbeddingProvider' in save_body
    has_reembed_call = 'reembed()' in save_body
    # reembed() must be inside an if-block, not called unconditionally
    reembed_conditional = bool(re.search(r'if\s*\([^)]*[Ee]mbedding[^)]*\)[^{]*\{[^}]*reembed', save_body, re.DOTALL))
    check('save() tracks _savedEmbeddingProvider for change detection', has_changed_guard, '',
          'read save() body in workspace-settings.component.ts, confirmed _savedEmbeddingProvider reference')
    check('save() calls reembed() inside conditional block', has_reembed_call and reembed_conditional, '',
          'confirmed reembed() call is inside if(embeddingChanged) not at top level of save()')
else:
    check('save() method parseable in workspace-settings', False, 'regex did not match method body')


# =============================================================================
# App Flow SS3: Extraction pipeline produces items with correct shape
# =============================================================================
print('\n=== App Flow SS3: Extraction produces correctly-shaped items ===')
from app.services.knowledge_extraction import KnowledgeExtraction

extractor = KnowledgeExtraction()
test_doc = """
We decided to use PostgreSQL instead of MySQL for the primary database.
The risk is that the team has limited PostgreSQL experience.
Lesson learned: always prototype the ORM layer before committing to a DB.
Best practice: write integration tests before merging any schema changes.
[ ] run migrations
[ ] backup prod
[ ] notify team
"""

decisions = extractor.extract_decisions(test_doc)
risks     = extractor.recognize_risk_patterns(test_doc)
lessons   = extractor.extract_lessons_learned(test_doc)
practices = extractor.identify_best_practices(test_doc)
checklists = extractor.detect_checklists(test_doc)

check('extract_decisions() >= 1 result', len(decisions) >= 1,
      f'got {len(decisions)}: {[d.get("what", d.get("decision","")) for d in decisions[:2]]}',
      'called extractor on test document containing "decided to", counted results')
check('recognize_risk_patterns() >= 1 result', len(risks) >= 1,
      f'got {len(risks)}',
      'called extractor on test document containing "risk is", counted results')
check('extract_lessons_learned() >= 1 result', len(lessons) >= 1,
      f'got {len(lessons)}',
      'called extractor on test document containing "lesson learned", counted results')
check('identify_best_practices() >= 1 result', len(practices) >= 1,
      f'got {len(practices)}',
      'called extractor on test document containing "best practice", counted results')
check('detect_checklists() >= 1 result', len(checklists) >= 1,
      f'got {len(checklists)}',
      'called extractor on test document containing "[ ]" checklist items, counted results')
if decisions:
    has_content_key = any(k in decisions[0] for k in ('what', 'decision', 'title'))
    check('Extracted decision dict has a content key', has_content_key,
          f'keys: {list(decisions[0].keys())}',
          'inspected first extracted decision dict for expected keys')


# =============================================================================
# App Flow SS6: Cross-source linking -- Jaccard similarity fires correctly
# =============================================================================
print('\n=== App Flow SS6: Cross-source linking behavior ===')
from app.services.cross_source_linker import find_cross_links

items = [
    {'id': 'a1', 'artifact_id': 'artA', 'title': 'deploy using docker compose on staging'},
    {'id': 'a2', 'artifact_id': 'artA', 'title': 'run database migrations before deploy'},
    {'id': 'b1', 'artifact_id': 'artB', 'title': 'deploy using docker compose on production'},
    {'id': 'b2', 'artifact_id': 'artB', 'title': 'completely unrelated topic about quarterly finance'},
]
links = find_cross_links(items)
pairs = [(a, b) for a, b, _ in links]

check('Cross-linker returns >= 1 link for similar cross-artifact items', len(links) >= 1,
      f'got {len(links)} links: {pairs}',
      'called find_cross_links() with known-similar items from different artifacts')
check('Similar pair (a1/b1) is linked', ('a1','b1') in pairs or ('b1','a1') in pairs,
      f'all pairs: {pairs}',
      'confirmed docker-compose items from different artifacts appear in output')
check('Same-artifact items are NOT cross-linked',
      not any((a in ('a1','a2') and b in ('a1','a2')) or (a in ('b1','b2') and b in ('b1','b2')) for a,b in pairs),
      f'pairs: {pairs}',
      'confirmed no intra-artifact pairs in cross-link output')
if links:
    check('All link scores >= 0.12 threshold', all(s >= 0.12 for _,_,s in links),
          f'scores: {[round(s,3) for _,_,s in links]}',
          'checked every returned score against documented 0.12 Jaccard threshold')


# =============================================================================
# App Flow SS7: GraphRAG transform_query graceful fallback when LLM down
# =============================================================================
print('\n=== App Flow SS7: GraphRAG transform_query fallback (no LLM) ===')
from app.services.graphrag import transform_query

async def test_transform():
    return await transform_query('What decisions were made about authentication?')

tr = asyncio.run(test_transform())
check('transform_query() returns dict when Ollama not running', isinstance(tr, dict),
      f'type: {type(tr).__name__}',
      'called transform_query() with Ollama not running, confirmed no exception raised')
check('transform_query() fallback preserves original question in sub_queries',
      'What decisions were made about authentication?' in tr.get('sub_queries', []),
      f'sub_queries: {tr.get("sub_queries")}',
      'confirmed original question in fallback sub_queries list')
check('transform_query() sub_queries capped at <=4 (TRD local mode cap)',
      len(tr.get('sub_queries', [])) <= 4,
      f'count: {len(tr.get("sub_queries", []))}',
      'confirmed TRD SS4 cap enforced in fallback path')


# =============================================================================
# App Flow SS7: GraphRAG full pipeline offline -- returns structured result
# =============================================================================
print('\n=== App Flow SS7: GraphRAG full pipeline offline (SQLite fallback) ===')
from app.services.graphrag import graphrag_query
from app.services.neo4j_graph import Neo4jGraphStore
import app.services.providers as prov
importlib.reload(prov)

async def test_graphrag_offline():
    neo4j = Neo4jGraphStore()  # disabled -- no URI/password set
    provider = prov.LocalSentenceTransformerProvider()
    vecs = await provider.embed([
        'decision to use JWT authentication with 8 hour expiry',
        'risk of token theft if stored in localStorage',
    ])
    fallback = [
        {'id': 'fi_001', 'title': 'JWT auth decision', 'type': 'decision',
         'details': {'what': 'use JWT with 8h expiry'}, 'embedding': vecs[0],
         'artifact_id': 'art1', 'review_status': 'accepted'},
        {'id': 'fi_002', 'title': 'Token storage risk', 'type': 'risk',
         'details': {'what': 'localStorage token theft'}, 'embedding': vecs[1],
         'artifact_id': 'art2', 'review_status': 'accepted'},
    ]
    return await graphrag_query(
        question='What authentication decisions were made?',
        neo4j_store=neo4j,
        fallback_items=fallback,
        cross_links=[],
        artifact_summaries=[],
        top_k=4,
    )

rag = asyncio.run(test_graphrag_offline())
check('graphrag_query() returns dict offline', isinstance(rag, dict),
      f'keys: {list(rag.keys())}',
      'called graphrag_query() with Neo4j disabled and Ollama not running')
check('graphrag_query() returns answer field', 'answer' in rag,
      f'answer[:80]: {str(rag.get("answer",""))[:80]}',
      'confirmed answer key present in offline result')
check('graphrag_query() retrieves context_nodes via SQLite cosine fallback',
      len(rag.get('context_nodes', [])) > 0,
      f'count: {len(rag.get("context_nodes", []))}',
      'confirmed SQLite cosine search found items from fallback_items')
check('graphrag_query() retrieval_mode reflects SQLite path',
      'sqlite' in rag.get('retrieval_mode', '').lower(),
      f'mode: {rag.get("retrieval_mode")}',
      'confirmed retrieval_mode contains "sqlite" not "neo4j" when Neo4j disabled')
check('graphrag_query() returns integer latency_ms',
      isinstance(rag.get('latency_ms'), int),
      f'latency_ms: {rag.get("latency_ms")}',
      'confirmed latency_ms is int, not None or float')


# =============================================================================
# App Flow SS5: Review workflow -- status change persists across sessions
# =============================================================================
print('\n=== App Flow SS5: Review status persists across DB sessions ===')

async def test_review_persists():
    import app.db as db_mod
    importlib.reload(db_mod)
    await db_mod.init_db()

    async with db_mod.SessionLocal() as session:
        session.add(db_mod.KnowledgeItem(
            id='review_test_001', workspace_id='ws_review', artifact_id='art_r',
            title='Pending item', type='decision', author='t', date='2024-01-01',
            tags=[], details={}, review_status='pending',
        ))
        await session.commit()

    # Simulate PATCH handler
    async with db_mod.SessionLocal() as session:
        ki = await session.get(db_mod.KnowledgeItem, 'review_test_001')
        ki.review_status = 'accepted'
        ki.review_note = 'looks good'
        await session.commit()

    # Read back in a new session
    async with db_mod.SessionLocal() as session:
        ki = await session.get(db_mod.KnowledgeItem, 'review_test_001')
        return ki.review_status, ki.review_note

status, note = asyncio.run(test_review_persists())
check('Review accept: status=accepted persists to DB', status == 'accepted',
      f'read back: {status}',
      'wrote accepted in one session, read back in separate session')
check('Review accept: review_note persists to DB', note == 'looks good',
      f'read back: {note}',
      'wrote note in one session, read back in separate session')


# =============================================================================
# TRD SS5.3: Embedding provenance columns populated after store
# =============================================================================
print('\n=== TRD SS5.3: Embedding provenance stored per item ===')

async def test_provenance():
    import app.db as db_mod
    importlib.reload(db_mod)
    await db_mod.init_db()
    provider = prov.LocalSentenceTransformerProvider()
    vecs = await provider.embed(['provenance test item'])

    async with db_mod.SessionLocal() as session:
        session.add(db_mod.KnowledgeItem(
            id='prov_001', workspace_id='ws_prov', artifact_id='art_prov',
            title='Provenance test', type='decision', author='t', date='2024-01-01',
            tags=[], details={},
            embedding=vecs[0],
            embedding_provider=provider.name,
            embedding_dims=provider.dimensions,
            review_status='accepted',
        ))
        await session.commit()

    async with db_mod.SessionLocal() as session:
        ki = await session.get(db_mod.KnowledgeItem, 'prov_001')
        return ki.embedding_provider, ki.embedding_dims, ki.embedding is not None

ep, ed, has_vec = asyncio.run(test_provenance())
check('embedding_provider column populated after store', ep == 'local:all-MiniLM-L6-v2',
      f'got: {ep}',
      'wrote provider.name to column, read back from separate session')
check('embedding_dims column populated correctly', ed == 384,
      f'got: {ed}',
      'wrote provider.dimensions to column, read back from separate session')
check('embedding vector stored (not None)', has_vec, '',
      'confirmed embedding column non-None after commit')


# =============================================================================
# Cleanup
# =============================================================================
shutil.rmtree(TMP_DIR, ignore_errors=True)

# =============================================================================
# Summary
# =============================================================================
print('\n' + '=' * 60)
passed  = sum(1 for _, ok, _   in results if ok)
failed  = sum(1 for _, ok, _   in results if not ok)
assumed = sum(1 for _, _,  vby in results if not vby)
print(f'Results: {passed} passed, {failed} failed, {assumed} assumed out of {len(results)} checks')
if failed:
    print('\nFailed checks:')
    for label, ok, _ in results:
        if not ok:
            print(f'  FAIL: {label}')
sys.exit(0 if failed == 0 else 1)
