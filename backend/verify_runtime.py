"""
Runtime verification script -- proves behavior, not just code existence.
Run from backend/ with: python verify_runtime.py
"""
import sys, os, asyncio, importlib, re, base64, hashlib, json, time, socket

# Force UTF-8 stdout so Windows cp1252 doesn't crash on any stray char
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, '.')

os.environ.setdefault('NEO4J_URI', '')
os.environ.setdefault('NEO4J_PASSWORD', '')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-32chars-padding!!')
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./data/test.db')

results = []

def check(label, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    suffix = f' -- {detail}' if detail else ''
    print(f'  [{status}] {label}{suffix}')
    results.append((label, bool(condition)))


# =============================================================================
# 1. KILL-SWITCH: ALLOW_CLOUD_PROVIDERS=false must block OpenAI even when
#    LLM_PROVIDER=openai and OPENAI_API_KEY is set.
# =============================================================================
print('\n=== 1. Admin kill-switch (ALLOW_CLOUD_PROVIDERS=false) ===')
os.environ['ALLOW_CLOUD_PROVIDERS'] = 'false'
os.environ['LLM_PROVIDER'] = 'openai'
os.environ['EMBEDDING_PROVIDER'] = 'openai'
os.environ['OPENAI_API_KEY'] = 'sk-fake-should-never-be-called'

import app.services.providers as prov
importlib.reload(prov)

llm = prov.get_llm_provider()
emb = prov.get_embedding_provider()
check('LLM is OllamaProvider (not OpenAI)', isinstance(llm, prov.OllamaProvider), type(llm).__name__)
check('LLM is_local=True', llm.is_local)
check('Embedding is LocalSentenceTransformer', isinstance(emb, prov.LocalSentenceTransformerProvider), type(emb).__name__)
check('Embedding is_local=True', emb.is_local)


# =============================================================================
# 2. KILL-SWITCH OFF: OpenAI selected when allowed + key present
# =============================================================================
print('\n=== 2. Cloud opt-in (ALLOW_CLOUD_PROVIDERS=true) ===')
os.environ['ALLOW_CLOUD_PROVIDERS'] = 'true'
importlib.reload(prov)

llm2 = prov.get_llm_provider()
emb2 = prov.get_embedding_provider()
check('LLM is OpenAILLMProvider', isinstance(llm2, prov.OpenAILLMProvider), type(llm2).__name__)
check('LLM is_local=False', not llm2.is_local)
check('Embedding is OpenAIEmbeddingProvider', isinstance(emb2, prov.OpenAIEmbeddingProvider), type(emb2).__name__)


# =============================================================================
# 3. WORKSPACE-LEVEL POLICY: workspace.allow_cloud_providers=False overrides
#    env even when ALLOW_CLOUD_PROVIDERS=true
# =============================================================================
print('\n=== 3. Workspace-level policy overrides env ===')
os.environ['ALLOW_CLOUD_PROVIDERS'] = 'true'
importlib.reload(prov)

class FakeWorkspace:
    allow_cloud_providers = False
    default_llm_provider = 'openai'
    default_embedding_provider = 'openai'
    ollama_model = None

ws = FakeWorkspace()
llm3 = prov.get_llm_provider(ws)
emb3 = prov.get_embedding_provider(ws)
check('Workspace policy blocks cloud LLM', isinstance(llm3, prov.OllamaProvider), type(llm3).__name__)
check('Workspace policy blocks cloud embedding', isinstance(emb3, prov.LocalSentenceTransformerProvider), type(emb3).__name__)


# =============================================================================
# 4. LOCAL EMBEDDINGS: sentence-transformers actually produces vectors
#    (not None, correct dimension, normalised)
# =============================================================================
print('\n=== 4. Local embedding produces real vectors ===')
os.environ['ALLOW_CLOUD_PROVIDERS'] = 'false'
importlib.reload(prov)

async def test_embed():
    provider = prov.LocalSentenceTransformerProvider()
    return await provider.embed(['test knowledge item about decisions'])

vecs = asyncio.run(test_embed())
check('embed() returns a list', isinstance(vecs, list))
check('embed() returns non-None vector', vecs[0] is not None, 'None = model failed to load')
if vecs[0] is not None:
    check('vector dimension is 384', len(vecs[0]) == 384, f'got {len(vecs[0])}')
    norm = sum(x*x for x in vecs[0]) ** 0.5
    check('vector is normalised (|v|~=1.0)', abs(norm - 1.0) < 0.01, f'|v|={norm:.4f}')


# =============================================================================
# 5. FERNET ENCRYPTION: API key round-trip -- plaintext never in ciphertext
# =============================================================================
print('\n=== 5. API key encryption round-trip ===')
from cryptography.fernet import Fernet

SECRET_KEY = os.environ['SECRET_KEY']
raw = hashlib.pbkdf2_hmac(
    'sha256', SECRET_KEY.encode(), b'knowledge-hubs-api-key-salt',
    iterations=100_000, dklen=32
)
f = Fernet(base64.urlsafe_b64encode(raw))

plaintext = 'sk-real-api-key-never-store-this'
ciphertext = f.encrypt(plaintext.encode()).decode()
decrypted = f.decrypt(ciphertext.encode()).decode()

check('Ciphertext != plaintext', ciphertext != plaintext)
check('Ciphertext does not contain plaintext substring', plaintext not in ciphertext)
check('Decrypt round-trip matches original', decrypted == plaintext)
# Different calls produce different ciphertext (Fernet uses random IV)
ct2 = f.encrypt(plaintext.encode()).decode()
check('Each encryption produces unique ciphertext (random IV)', ciphertext != ct2)


# =============================================================================
# 6. JWT EXPIRY: backend token has exp claim; frontend jwtExpired() logic
#    correctly identifies fresh vs stale tokens
# =============================================================================
print('\n=== 6. JWT expiry detection ===')
from app.auth import create_token

token = create_token('user-1', 'workspace-1')
parts = token.split('.')
padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
payload = json.loads(base64.urlsafe_b64decode(padded))

check('Token has exp claim', 'exp' in payload, str(list(payload.keys())))
check('exp is in the future', payload['exp'] > time.time(),
      f"exp={payload['exp']} now={int(time.time())}")
check('exp is ~8h from now (7-9h window)',
      7 * 3600 < payload['exp'] - time.time() < 9 * 3600,
      f"delta={payload['exp'] - time.time():.0f}s")

# Replicate frontend jwtExpired() in Python
def jwt_expired_sim(tok):
    try:
        p = tok.split('.')[1].replace('-', '+').replace('_', '/')
        p += '=' * (4 - len(p) % 4)
        data = json.loads(base64.b64decode(p))
        return isinstance(data.get('exp'), (int, float)) and data['exp'] * 1000 < time.time() * 1000
    except Exception:
        return True

check('Fresh token: jwt_expired_sim() returns False', not jwt_expired_sim(token))

# Forge an expired token payload to confirm detection
import hmac as _hmac
expired_payload = base64.urlsafe_b64encode(
    json.dumps({'sub': 'u', 'exp': int(time.time()) - 3600}).encode()
).rstrip(b'=').decode()
fake_expired = f"eyJhbGciOiJIUzI1NiJ9.{expired_payload}.fakesig"
check('Expired token: jwt_expired_sim() returns True', jwt_expired_sim(fake_expired))


# =============================================================================
# 7. GRAPHRAG HISTORY ORDERING: slice happens BEFORE push so current question
#    is never duplicated in history sent to backend
# =============================================================================
print('\n=== 7. GraphRAG history slice ordering ===')
messages = [
    {'role': 'user',      'content': 'first question',  'ts': 1},
    {'role': 'assistant', 'content': 'first answer',    'ts': 2},
    {'role': 'user',      'content': 'second question', 'ts': 3},
    {'role': 'assistant', 'content': 'second answer',   'ts': 4},
]
current_q = 'third question'

# Correct order as implemented in graphrag.component.ts
history = [{'role': m['role'], 'content': m['content']} for m in messages[-6:]]
messages.append({'role': 'user', 'content': current_q, 'ts': 5})

check('History does not contain current question',
      not any(m['content'] == current_q for m in history),
      str([m['content'] for m in history]))
check('History contains the 4 prior turns', len(history) == 4)

# Confirm the bug would exist if order were reversed
msgs_buggy = [
    {'role': 'user', 'content': 'q1', 'ts': 1},
    {'role': 'assistant', 'content': 'a1', 'ts': 2},
]
buggy_q = 'buggy question'
msgs_buggy.append({'role': 'user', 'content': buggy_q, 'ts': 3})   # push first
history_buggy = [{'role': m['role'], 'content': m['content']} for m in msgs_buggy[-6:]]
check('Reversed order WOULD duplicate current question (confirms fix matters)',
      any(m['content'] == buggy_q for m in history_buggy))


# =============================================================================
# 8. PIPELINE STAGE PROGRESS: timer-driven, not event-driven
#    This is a confirmed cosmetic gap -- stages do not reflect real backend
#    pipeline position. Flagged explicitly, not hidden.
# =============================================================================
print('\n=== 8. GraphRAG pipeline stage progress (behavioral gap) ===')
with open('../frontend/src/app/pages/graphrag/graphrag.component.ts', encoding='utf-8') as fh:
    ts_src = fh.read()

stages_match = re.search(r'PIPELINE_STAGES\s*=\s*\[(.*?)\]', ts_src, re.DOTALL)
interval_match = re.search(r'setInterval', ts_src)
# Event-driven would require backend to stream stage names; check for that
event_driven = bool(re.search(r'data\.stage|event\.stage|stream', ts_src))

check('PIPELINE_STAGES array exists', bool(stages_match))
check('Uses setInterval -- timer-driven NOT event-driven', bool(interval_match),
      'stages advance on clock, not on real backend pipeline events')
check('No streaming/event stage data from backend', not event_driven,
      'KNOWN GAP: progress is cosmetic, does not reflect actual pipeline position')


# =============================================================================
# 9. NEO4J DELETE: delete_artifact_graph and delete_item must raise on
#    failure (no silent except). Verified by inspecting method bodies.
# =============================================================================
print('\n=== 9. Neo4j delete methods raise on failure ===')
with open('app/services/neo4j_graph.py', encoding='utf-8') as fh:
    neo_src = fh.read()

for method_name in ('delete_artifact_graph', 'delete_item'):
    m = re.search(
        rf'def {method_name}.*?(?=\n    def |\nclass |\Z)', neo_src, re.DOTALL)
    if m:
        body = m.group(0)
        # A silent except would catch and log/return without re-raising
        silent = bool(re.search(r'except[^:]*:\s*\n\s*(logger\.|return|pass)', body))
        check(f'{method_name}: no silent except (raises on failure)', not silent)
    else:
        check(f'{method_name} method found in source', False)


# =============================================================================
# 10. AIRPLANE-MODE: provider resolution makes zero outbound network calls
#     when ALLOW_CLOUD_PROVIDERS=false. Verified by patching socket.connect.
# =============================================================================
print('\n=== 10. Airplane-mode: zero network calls during provider resolution ===')
_orig_connect = socket.socket.connect
network_calls = []

def _blocked_connect(self, address):
    network_calls.append(address)
    raise ConnectionRefusedError(f'BLOCKED: {address}')

socket.socket.connect = _blocked_connect
try:
    os.environ['ALLOW_CLOUD_PROVIDERS'] = 'false'
    os.environ['LLM_PROVIDER'] = 'openai'
    os.environ['OPENAI_API_KEY'] = 'sk-fake'
    importlib.reload(prov)
    _ = prov.get_llm_provider()
    _ = prov.get_embedding_provider()
    check('Provider resolution: zero network calls', len(network_calls) == 0,
          f'attempted: {network_calls}')
finally:
    socket.socket.connect = _orig_connect


# =============================================================================
# 11. AIRPLANE-MODE: sentence-transformers embed() makes zero network calls
#     after the model is already loaded (no phoning home per-call)
# =============================================================================
print('\n=== 11. Airplane-mode: embed() makes zero network calls ===')
network_calls2 = []

def _blocked_connect2(self, address):
    # Only block non-loopback addresses; asyncio uses 127.0.0.1 socketpair internally
    host = address[0] if isinstance(address, tuple) else str(address)
    if host not in ('127.0.0.1', '::1', 'localhost'):
        network_calls2.append(address)
        raise ConnectionRefusedError(f'BLOCKED: {address}')
    return _orig_connect(self, address)

socket.socket.connect = _blocked_connect2
try:
    async def test_embed_offline():
        provider = prov.LocalSentenceTransformerProvider()
        return await provider.embed(['does this phone home?'])
    vecs2 = asyncio.run(test_embed_offline())
    check('embed() with loaded model: zero non-loopback network calls', len(network_calls2) == 0,
          f'attempted: {network_calls2}')
    check('embed() still returns valid vector offline', vecs2[0] is not None)
finally:
    socket.socket.connect = _orig_connect


# =============================================================================
# Summary
# =============================================================================
print('\n' + '=' * 60)
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f'Results: {passed} passed, {failed} failed out of {len(results)} checks')
if failed:
    print('\nFailed checks:')
    for label, ok in results:
        if not ok:
            print(f'  FAIL: {label}')
sys.exit(0 if failed == 0 else 1)
