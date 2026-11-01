"""Real-clock playback regression. Serve the production dashboard at loopback 4192.
No virtual clock, inference, page reconstruction or private trace loading.
"""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
EVENTS=json.loads((ROOT/'src/fixtures/ironbark-s1-recorded.json').read_text())['storyboard']['steps']
URL='http://127.0.0.1:4192/'
with sync_playwright() as pw:
 browser=pw.chromium.launch(args=['--no-sandbox'])
 for width,motion in [(1440,'no-preference'),(390,'reduce')]:
  context=browser.new_context(viewport={'width':width,'height':1080 if width==1440 else 844},reduced_motion=motion)
  blocked=[];errors=[]
  def route(r):
   if r.request.url.startswith(URL):r.continue_()
   else:blocked.append(r.request.url);r.abort()
  context.route('**/*',route);page=context.new_page();page.set_default_timeout(6000)
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL,wait_until='networkidle')
  def synchronized(i):
   expect(page.locator('.studio-action')).to_have_attribute('data-event-ref',f'/storyboard/steps/{i}')
   expect(page.locator('.studio-action h3')).to_have_text(EVENTS[i]['text'])
   expect(page.locator('.studio-inspector dd').first).to_have_text(EVENTS[i]['text'])
   expect(page.locator('.inspector-heading')).to_contain_text(f'{i+1} / {len(EVENTS)}')
   expect(page.locator('.transport')).to_contain_text(f'Step {i+1} / {len(EVENTS)}')
   expect(page.get_by_role('slider')).to_have_value(str(i))
   expect(page.locator('.studio-events button[aria-current] > span')).to_have_text(f'{i+1:02}')
   expect(page.locator('.replay-state strong')).to_have_text(f'Entry {i+1} of {len(EVENTS)}')
  synchronized(0)
  # Prove no autoplay and pause stability beyond a full presentation interval.
  page.wait_for_timeout(2400);synchronized(0)
  page.get_by_role('button',name='Play',exact=True).click();synchronized(1)
  page.get_by_role('button',name='Pause',exact=True).click();page.wait_for_timeout(2500);synchronized(1)
  page.get_by_role('button',name='Restart replay').click();synchronized(0)
  page.get_by_role('button',name='Play',exact=True).click();started=time.monotonic()
  for i in range(1,len(EVENTS)):
   synchronized(i)
   print(f'{width}px timed event {i+1}/{len(EVENTS)} at {time.monotonic()-started:.2f}s; all UI synchronized',flush=True)
  expect(page.get_by_role('button',name='Play',exact=True)).to_be_disabled()
  page.wait_for_timeout(2400);synchronized(len(EVENTS)-1)
  # Restart while playing cancels its pending timer.
  page.get_by_role('button',name='Restart replay').click();page.get_by_role('button',name='Play',exact=True).click()
  page.get_by_role('button',name='Restart replay').click();page.wait_for_timeout(2400);synchronized(0)
  # Native range keyboard scrub during playback pauses at an exact source entry.
  page.get_by_role('button',name='Play',exact=True).click()
  slider=page.get_by_role('slider');slider.focus();slider.press('End');synchronized(len(EVENTS)-1)
  page.wait_for_timeout(2400);synchronized(len(EVENTS)-1)
  page.get_by_role('button',name='Restart replay').click();page.get_by_role('button',name='Play',exact=True).click()
  page.locator('.studio-events button').nth(3).focus();page.keyboard.press('Enter')
  page.wait_for_timeout(2400);synchronized(3)
  # Repetitive scroll identity and special fallback are independent of action text.
  for i in [2,3,4,5]:
   page.locator('.studio-events button').nth(i).click();synchronized(i)
   if i<5:
    if not page.locator('.event-technical').evaluate('(n)=>n.open'):page.locator('.event-technical summary').click()
    expect(page.locator('.scroll-evidence-note')).to_be_visible()
   else:expect(page.locator('.tool-action')).to_be_visible()
  page.locator('.studio-events button').nth(3).click();synchronized(3)
  if page.locator('.event-technical').evaluate('(n)=>n.open'):page.locator('.event-technical summary').click()
  assert page.evaluate(f'document.documentElement.scrollWidth==={width}')
  if motion=='reduce':assert page.locator('.studio-action').evaluate("n=>getComputedStyle(n).animationName==='none'")
  page.screenshot(path=str(ROOT/'review'/f'playback-{width}.png'),full_page=True,animations='disabled')
  assert not errors,errors
  assert not blocked,blocked
  context.close()
 browser.close()
print('PASS: real-clock desktop/mobile full playback, synchronized UI, pause/end/restart, keyboard scrubbing/manual selection, repeated scroll identity, reduced motion and no external requests.')
