from pathlib import Path
from playwright.sync_api import sync_playwright

def test_panel_interactions(tmp_path):
    p=Path(__file__).resolve().parents[1]/'index.html'
    with sync_playwright() as w:
     browser=w.chromium.launch(headless=True)
     page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
     errors=[];page.on('pageerror',lambda x:errors.append(str(x)));page.goto(p.as_uri());page.wait_for_timeout(200)
     page.screenshot(path=str(tmp_path/'margin-panel-desktop.png'),full_page=True)
     print('initial',page.locator('.reading').all_text_contents(),page.locator('.period').all_text_contents())
     for label in ['1m','3m','6m','ytd','1y','3y','5y','all','2017']:
      page.locator(f'[data-range="{label}"]').click();assert page.locator('.series').count()==2
      assert page.locator(f'[data-range="{label}"]').get_attribute('aria-pressed')=='true'
     page.locator('[data-range="ytd"]').click();page.screenshot(path=str(tmp_path/'margin-panel-ytd.png'),full_page=True)
     assert page.locator('#from').input_value()=='2026-01-01'
     plot=page.locator('#financing .plot');b=plot.bounding_box();page.mouse.move(b['x']+b['width']*.5,b['y']+b['height']*.5)
     dates=page.locator('.reading time').all_text_contents();assert dates[0]==dates[1] and dates[0]<'2026-10-30',dates
     page.screenshot(path=str(tmp_path/'margin-panel-hover.png'),full_page=True)
     plot.focus();page.keyboard.press('ArrowLeft');assert page.locator('#financing time').inner_text()<dates[0]
     old=page.locator('#financing svg').get_attribute('data-y-max');axis=page.locator('#financing .axis-hit');bb=axis.bounding_box()
     page.mouse.move(bb['x']+20,bb['y']+70);page.mouse.down();page.mouse.move(bb['x']+20,bb['y']+140,steps=10);page.mouse.up();page.wait_for_timeout(100)
     assert page.locator('#financing svg').get_attribute('data-y-max')!=old
     page.locator('#financing .reset').click();assert page.locator('#financing svg').get_attribute('data-y-max')==old
     page.locator('#from').fill('2024-01-01');page.locator('#from').dispatch_event('change');page.locator('#to').fill('2024-12-31');page.locator('#to').dispatch_event('change');assert page.locator('#financing .period').inner_text().startswith('2024-01-02')
     page.locator('#from').fill('2025-01-01');page.locator('#from').dispatch_event('change');assert page.locator('#date-error').inner_text()
     assert not errors,errors
     mobile=browser.new_page(viewport={'width':360,'height':900},device_scale_factor=1,is_mobile=True,has_touch=True)
     mobile.on('pageerror',lambda x:errors.append(str(x)));mobile.goto(p.as_uri());mobile.wait_for_timeout(200)
     assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
     mobile.screenshot(path=str(tmp_path/'margin-panel-mobile.png'),full_page=True)
     mobile.locator('[data-range="ytd"]').tap();mb=mobile.locator('#lending .plot').bounding_box();mobile.touchscreen.tap(mb['x']+mb['width']*.5,mb['y']+100)
     dates=mobile.locator('.reading time').all_text_contents();assert dates[0]==dates[1] and dates[0]<'2026-10-30',dates
     mobile.screenshot(path=str(tmp_path/'margin-panel-mobile-touch.png'),full_page=True)
     narrow=browser.new_page(viewport={'width':320,'height':820},device_scale_factor=1,is_mobile=True,has_touch=True);narrow.goto(p.as_uri());narrow.wait_for_timeout(200)
     assert narrow.evaluate('document.documentElement.scrollWidth<=innerWidth')
     narrow.screenshot(path=str(tmp_path/'margin-panel-narrow.png'),full_page=True)
     print('PASS desktop/mobile/narrow; all presets/custom/invalid dates; hover/touch/keyboard; axis drag/reset; console',errors)
     browser.close()
