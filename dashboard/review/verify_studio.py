"""Offline browser rehearsal. Serve dashboard/dist on loopback port 4192 first."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
URL='http://127.0.0.1:4192/'
source=json.loads((ROOT/'src/fixtures/ironbark-s1-recorded.json').read_text())
with sync_playwright() as pw:
 browser=pw.chromium.launch(args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':1440,'height':1080})
 blocked=[]
 def route(r):
  if r.request.url.startswith(URL):r.continue_()
  else:blocked.append(r.request.url);r.abort()
 context.route('**/*',route)
 page=context.new_page();page.set_default_timeout(10000)
 errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto(URL,wait_until='networkidle')
 assert page.locator('.studio-action h3').inner_text()==source['storyboard']['steps'][0]['text']
 assert page.get_by_role('button',name='Play',exact=True).is_enabled()
 assert page.locator('.studio-events button').count()==len(source['storyboard']['steps'])
 assert page.evaluate("[...document.fonts].some(f=>f.family==='Geist'&&f.status==='loaded')")
 page.get_by_role('button',name='Play',exact=True).click()
 page.wait_for_function("document.querySelector('.studio-action').dataset.eventRef === '/storyboard/steps/1'")
 page.get_by_role('button',name='Pause',exact=True).click()
 page.get_by_role('button',name='Previous event',exact=True).click()
 slider=page.get_by_role('slider',name='Replay position');slider.focus();slider.press('ArrowRight')
 assert page.locator('.studio-action h3').inner_text()==source['storyboard']['steps'][1]['text']
 assert source['storyboard']['steps'][1]['text'] in page.get_by_role('complementary',name='Evidence inspector').inner_text()
 page.locator('.studio-events button').nth(7).click()
 assert page.locator('.studio-action h3').inner_text()==source['storyboard']['steps'][7]['text']
 page.screenshot(path=str(OUT/'desktop.png'),full_page=True,animations='disabled')
 page.get_by_role('button',name='Restart replay').click()
 page.get_by_label('Task',exact=True).select_option(source['tasks'][1]['task_id'])
 assert page.get_by_text('Public replay unavailable',exact=True).is_visible()
 assert page.get_by_role('button',name='Play',exact=True).is_disabled()
 page.get_by_label('Task',exact=True).select_option(source['storyboard']['task_id'])
 page.get_by_text('Report sources & technical details',exact=True).click()
 page.get_by_label('Load a reviewed public report',exact=True).set_input_files(ROOT/'src/fixtures/ironbark-s1-recorded.json')
 expect(page.locator('.studio-action')).to_have_attribute('data-event-ref','/storyboard/steps/0')
 page.get_by_role('button',name='Next event',exact=True).click()
 page.get_by_label('Load a reviewed public report',exact=True).set_input_files(ROOT/'src/fixtures/ironbark-s1-recorded.json')
 expect(page.locator('.studio-action')).to_have_attribute('data-event-ref','/storyboard/steps/0')
 page.get_by_label('Load a reviewed public report',exact=True).set_input_files({'name':'rejected.json','mimeType':'application/json','buffer':b'{"raw_trace":"withheld"}'})
 expect(page.get_by_role('alert')).to_be_visible()
 page.get_by_role('button',name='Classic dashboard',exact=False).click()
 page.locator('.product-story').wait_for()
 assert page.locator('.product-story li').count()==len(source['storyboard']['steps'])
 page.get_by_role('link',name='Replay Studio',exact=True).click()
 page.set_viewport_size({'width':390,'height':844});page.emulate_media(reduced_motion='reduce')
 page.locator('.studio-action').wait_for()
 assert page.evaluate('document.documentElement.scrollWidth===390')
 assert page.locator('.studio-action').evaluate("n=>getComputedStyle(n).animationName==='none'")
 page.get_by_role('button',name='Next event',exact=True).focus();page.keyboard.press('Enter')
 assert page.locator('.studio-action h3').inner_text()==source['storyboard']['steps'][1]['text']
 assert page.locator('button:focus-visible').count()==1
 page.screenshot(path=str(OUT/'narrow.png'),full_page=True,animations='disabled')
 assert not errors,errors
 assert not blocked,blocked
 context.close();browser.close()
print('PASS: backend-free desktop/narrow playback, pause/restart/step, keyboard scrub/activation, event/inspector sync, import/rejection, missing task evidence, fallback report, local Geist, reduced motion, no overflow/page errors/external requests.')
