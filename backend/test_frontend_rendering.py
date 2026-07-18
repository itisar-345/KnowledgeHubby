"""
Verifies two things:
1. The exact string the backend produces when LLM is unavailable.
2. That the frontend template renders it verbatim with no intercept.
"""
import sys, os, asyncio, re
sys.path.insert(0, '.')
os.environ['ALLOW_CLOUD_PROVIDERS'] = 'false'
os.environ['NEO4J_URI'] = ''
os.environ['NEO4J_PASSWORD'] = ''
os.environ['SECRET_KEY'] = 'test-key'

results = []
def check(label, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'  [{status}] {label}' + (f' -- {detail}' if detail else ''))
    results.append((label, bool(condition)))

# ── 1. Backend: what does _generate() return when Ollama is down? ─────────────
print('\n=== 1. Backend answer string when LLM unavailable ===')
from app.services.graphrag import _generate

async def get_offline_answer():
    context = (
        '=== KNOWLEDGE ITEMS ===\n'
        '[item_001] (decision) relevance=0.821: JWT auth decision\n'
        '  what: use JWT with 8h expiry'
    )
    return await _generate(
        'What auth decisions were made?', context, 'factual',
        history=None, workspace=None
    )

answer = asyncio.run(get_offline_answer())
print(f'  answer = {repr(answer[:120])}')
print()

check('Answer starts with [LLM unavailable]', answer.startswith('[LLM unavailable]'),
      f'got: {answer[:40]}')
check('Answer contains the context preview (not empty/generic)',
      'JWT' in answer or 'KNOWLEDGE' in answer or 'item_001' in answer,
      f'answer[:80]: {answer[:80]}')
check('Answer is not a generic error string',
      'Error' not in answer and 'failed' not in answer.lower(),
      f'answer[:80]: {answer[:80]}')

# ── 2. Frontend: how is data.answer rendered? ─────────────────────────────────
print('\n=== 2. Frontend rendering chain ===')
with open('../frontend/src/app/pages/graphrag/graphrag.component.ts', encoding='utf-8') as f:
    src = f.read()

# Find the line that assigns data.answer to the message
assign_match = re.search(r'content:\s*data\.answer', src)
check('data.answer assigned directly to message.content',
      bool(assign_match),
      assign_match.group(0) if assign_match else 'not found')

# Find the template line that renders message content
render_match = re.search(r'\{\{\s*m\.content\s*\}\}', src)
check('Template renders m.content verbatim via {{ m.content }}',
      bool(render_match),
      render_match.group(0) if render_match else 'not found')

# Check for any conditional that checks the answer string before rendering
has_answer_condition = bool(re.search(
    r'(if|ngIf|\*ngIf|@if).*?(answer|content).*?(unavailable|error|failed)',
    src, re.IGNORECASE
))
check('No conditional hides/replaces answer based on content',
      not has_answer_condition,
      'found conditional on answer content' if has_answer_condition else 'clean')

# Check the catch block — what renders on HTTP error (network failure, 401, etc.)
catch_match = re.search(r'catch\s*\(e[^)]*\)\s*\{([^}]+)\}', src, re.DOTALL)
if catch_match:
    catch_body = catch_match.group(1).strip()
    print(f'\n  catch block body: {catch_body[:200]}')
    catch_uses_error_msg = 'e?.message' in catch_body or "e?.error" in catch_body
    catch_pushes_message = 'messages.push' in catch_body
    check('catch block pushes a message (not silent)',
          catch_pushes_message, catch_body[:80])
    check('catch block uses actual error message (not generic string)',
          catch_uses_error_msg, catch_body[:80])
else:
    check('catch block found', False, 'regex did not match')

# ── 3. The gap: HTTP error vs LLM-unavailable are different paths ─────────────
print('\n=== 3. Two distinct failure paths ===')
print('  Path A: Ollama down, backend still responds HTTP 200')
print('          -> data.answer = "[LLM unavailable] Relevant context..."')
print('          -> frontend renders this verbatim. User sees honest message.')
print()
print('  Path B: Backend itself crashes / network error / 401')
print('          -> catch block fires')
print('          -> frontend renders: Error: <e.message>')
print()

# Check whether the catch path gives enough info
catch_content = catch_match.group(1) if catch_match else ''
error_detail = 'e?.error?.detail' in catch_content or 'e?.message' in catch_content
check('Path B (HTTP error) surfaces error detail, not just "Request failed"',
      error_detail,
      catch_content.strip()[:120] if catch_content else 'no catch body')

# ── Summary ───────────────────────────────────────────────────────────────────
print('\n' + '=' * 60)
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f'Results: {passed} passed, {failed} failed out of {len(results)} checks')
if failed:
    print('\nFailed:')
    for label, ok in results:
        if not ok:
            print(f'  FAIL: {label}')
sys.exit(0 if failed == 0 else 1)
