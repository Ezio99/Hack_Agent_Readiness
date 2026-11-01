"""Recapture optional, unmodified UI crops from the current default recorded dashboard.

This utility only supports the dashboard's existing default public fixture. It does
not load another run into the dashboard, alter its data or invoke any backend.
"""
import asyncio
import hashlib
import json
from pathlib import Path
from playwright.async_api import async_playwright
from evidence_adapter import load, local_path

ROOT = Path(__file__).resolve().parent


async def main():
    manifest = json.loads((ROOT / 'demo-manifest.json').read_text())
    evidence = load(ROOT, manifest)
    asset = ROOT.parent / 'dashboard/src/fixtures/ironbark-s1-recorded.json'
    if local_path(ROOT, manifest['evidence']['source']) != asset.resolve():
        raise ValueError('Capture only supports the current dashboard default fixture')
    data = json.loads(asset.read_text())
    if manifest['featured']['task_id'] != data['storyboard']['task_id']:
        raise ValueError('Default dashboard does not show the selected task')
    selectors = {'recorded-storyboard': '.product-story', 'recorded-suggestion': '.suggestion-card',
                 'recorded-outcomes': '#product-measure .table-wrap'}
    records = {}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1365, 'height': 1800}, device_scale_factor=1)
        await page.route('**/*', lambda route: route.continue_() if route.request.url.startswith('http://127.0.0.1:4190/') else route.abort())
        await page.goto('http://127.0.0.1:4190/', wait_until='networkidle')
        await page.locator('.product-story').wait_for(state='attached')
        assert await page.locator('.product-story li').count() == len(data['storyboard']['steps'])
        for index, step in enumerate(data['storyboard']['steps']):
            assert step['text'] in await page.locator('.product-story li').nth(index).inner_text()
        for name, selector in selectors.items():
            path = ROOT / 'assets' / f'{name}.png'
            await page.locator(selector).evaluate('(node) => node.scrollIntoView({block: "center"})')
            await page.locator(selector).screenshot(path=str(path), animations='disabled')
            records[path.name] = {'selector': selector, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        await browser.close()
    metadata = {'dashboard_base': '4eac56a', 'recorded_asset_sha256': evidence['source_sha256'],
                'source': str(asset.relative_to(ROOT.parent)), 'viewport': {'width': 1365, 'height': 1800},
                'capture': 'Unmodified local static dashboard, no backend or model; selected component screenshots.',
                'images': records, 'task_id': data['storyboard']['task_id'], 'arm': data['storyboard']['arm'],
                'proposal_id': manifest['evidence']['proposal_id'],
                'story_event_refs': [f'/storyboard/steps/{i}' for i in range(len(data['storyboard']['steps']))]}
    (ROOT / 'assets/capture-provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
