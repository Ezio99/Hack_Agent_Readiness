"""Build and render static frames; exercise replacement paths entirely offline."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from playwright.async_api import async_playwright
from build import build
from evidence_adapter import project

ROOT = Path(__file__).resolve().parent


async def replacement_checks(browser, payload, manifest):
    """Alternate data stays in browser memory and is never exported as evidence."""
    css = (ROOT / 'film.css').read_text()
    js = (ROOT / 'scenes.js').read_text()
    report = json.loads((ROOT / manifest['evidence']['source']).read_text())
    alternate = copy.deepcopy(payload)
    candidate = next((t for t in report['tasks'] if t['task_id'] != manifest['featured']['task_id']), report['tasks'][0])
    featured = manifest['featured'] | {'task_id': candidate['task_id']}
    # Test scenes independently of configured order or optional visibility.
    alternate['scenes'] = [
        {'id': '03-behavior', 'component': 'behavior', 'headline': ['Inspect this task.'],
         'emphasis': 'focus-event', 'provenance': 'Test-only composed view'},
        {'id': '05-results', 'component': 'results', 'headline': ['Test-only counts.'],
         'emphasis': 'metrics'}
    ]
    alternate['evidence'] = project(report, manifest['evidence'], featured, 'test-only')
    alternate['captures'] = {}
    page = await browser.new_page(viewport={'width':1920,'height':1080})
    await page.route('**/*', lambda route: route.abort())
    await page.set_content(f'<style>{css}</style><body class="frame" data-scene="03-behavior"><main></main></body>')
    await page.evaluate('(payload) => window.FILM=payload', alternate)
    await page.add_script_tag(content=js)
    assert await page.locator('h1').inner_text() == 'Inspect this task.'
    assert candidate['question'] in await page.locator('.archive').inner_text()
    if not alternate['evidence']['featured']['events']:
        assert 'No public event sequence' in await page.locator('.archive').inner_text()
    assert await page.locator('img').count() == 0
    # Stress longer counts and missing fields through the same results component.
    alternate['evidence']['task_count'] = 12345
    alternate['evidence']['original']['supported'] = 1234
    alternate['evidence']['modified']['supported'] = None
    alternate['evidence']['original']['requests'] = 123456789
    alternate['evidence']['modified']['requests'] = 98765432
    alternate['evidence']['request_change_label'] = 'Test-only replacement; never exported'
    await page.set_content(f'<style>{css}</style><body class="frame" data-scene="05-results"><main></main></body>')
    await page.evaluate('(payload) => window.FILM=payload', alternate)
    await page.add_script_tag(content=js)
    assert '1,234/12,345' in await page.locator('[data-metric="passes"]').inner_text()
    assert '—/12,345' in await page.locator('[data-metric="passes"]').inner_text()
    assert await page.locator('.metric-value').evaluate_all('(nodes)=>nodes.every(n=>n.scrollWidth<=n.clientWidth)')
    await page.close()


async def main(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    payload = build(manifest_path)
    frames = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width':1920,'height':1080}, device_scale_factor=1)
        page.set_default_timeout(10000)
        requests = []
        async def block(route):
            requests.append(route.request.url)
            await route.abort()
        await page.route('http**://**', block)
        for scene in payload['scenes']:
            errors = []
            handler = lambda error: errors.append(str(error))
            page.on('pageerror', handler)
            frame = ROOT / 'frames' / f"{scene['id']}.html"
            await page.goto(frame.as_uri(), wait_until='load')
            await page.evaluate('document.fonts.ready')
            assert await page.locator('h1').count() == 1
            assert await page.evaluate('document.documentElement.scrollWidth===1920 && document.documentElement.scrollHeight===1080')
            assert await page.locator('img').evaluate_all('(imgs)=>imgs.every(i=>i.complete && i.naturalWidth>0)')
            assert not errors, errors
            assert await page.locator('h1').evaluate('(n)=>n.getBoundingClientRect().right<=1761')
            assert await page.locator('.proof').evaluate('(n)=>n.getBoundingClientRect().right<=1761')
            out = ROOT / 'exports' / f"{scene['id']}.png"
            await page.screenshot(path=str(out))
            frames.append({'frame':scene['id'], 'width':1920, 'height':1080,
                           'sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
            # Inspect the real half-scale layout without saving alternate evidence.
            await page.set_viewport_size({'width':960,'height':540})
            await page.evaluate("document.body.style.zoom='0.5'")
            assert await page.locator('.stage').evaluate('(n)=>n.getBoundingClientRect().width===960 && n.getBoundingClientRect().height===540')
            await page.set_viewport_size({'width':1920,'height':1080})
            page.remove_listener('pageerror', handler)
        await page.set_viewport_size({'width':1920,'height':1900})
        await page.goto((ROOT / 'index.html').as_uri(), wait_until='load')
        assert await page.locator('img').count() == len(frames)
        assert await page.locator('img').evaluate_all('(imgs)=>imgs.every(i=>i.complete && i.naturalWidth===1920)')
        await page.screenshot(path=str(ROOT / 'exports/contact-sheet.png'), full_page=True)
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth===390')
        await page.keyboard.press('Tab')
        assert await page.locator('a:focus').count() == 1
        assert not requests, requests
        await replacement_checks(browser, payload, manifest)
        await browser.close()
    (ROOT / 'exports/render-manifest.json').write_text(json.dumps({
        'format':'Static Checkpoint A; no animation', 'source_sha256':payload['evidence']['source_sha256'],
        'demo_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'checks':['images loaded', 'no page errors', '1920x1080', 'safe headline/footer bounds', '50% scale',
                  'no external requests', '390px contact sheet and keyboard focus', 'alternate task/copy',
                  'missing values and long numbers'], 'frames':frames}, indent=2) + '\n')
    print(f'Rendered {len(frames)} static 1920x1080 frames and contact sheet. Offline browser and replacement checks passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=ROOT / 'demo-manifest.json')
    asyncio.run(main(parser.parse_args().manifest))
