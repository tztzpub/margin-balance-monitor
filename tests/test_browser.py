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
     plot=page.locator('#financing .plot');plot.scroll_into_view_if_needed();plot.focus();page.wait_for_timeout(250);b=plot.bounding_box();page.mouse.move(b['x']+b['width']*.5,b['y']+b['height']*.5)
     dates=page.locator('.reading time').all_text_contents();assert dates[0]==dates[1] and dates[0]<'2026-10-30',dates
     page.screenshot(path=str(tmp_path/'margin-panel-hover.png'),full_page=True)
     plot.focus();page.keyboard.press('ArrowLeft');assert page.locator('#financing .reading time').inner_text()<dates[0]
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
     mobile.locator('[data-range="ytd"]').tap();mobile.locator('#lending .plot').scroll_into_view_if_needed();mb=mobile.locator('#lending .plot').bounding_box();mobile.touchscreen.tap(mb['x']+mb['width']*.5,mb['y']+100)
     dates=mobile.locator('.reading time').all_text_contents();assert dates[0]==dates[1] and dates[0]<'2026-10-30',dates
     mobile.screenshot(path=str(tmp_path/'margin-panel-mobile-touch.png'),full_page=True)
     narrow=browser.new_page(viewport={'width':320,'height':820},device_scale_factor=1,is_mobile=True,has_touch=True);narrow.goto(p.as_uri());narrow.wait_for_timeout(200)
     assert narrow.evaluate('document.documentElement.scrollWidth<=innerWidth')
     narrow.screenshot(path=str(tmp_path/'margin-panel-narrow.png'),full_page=True)
     print('PASS desktop/mobile/narrow; all presets/custom/invalid dates; hover/touch/keyboard; axis drag/reset; console',errors)
     browser.close()

def test_lookback_anchor_uses_full_trading_history(tmp_path):
    import pandas as pd
    root=Path(__file__).resolve().parents[1]
    dates=pd.read_csv(root/'data/financing_accounts_daily.csv')['date'].to_list()
    with sync_playwright() as w:
        browser=w.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1250})
        page.goto((root/'index.html').as_uri());page.wait_for_timeout(120)
        assert not page.locator('#financing .lookback').is_visible()
        page.locator('#financing .plot').scroll_into_view_if_needed()
        box=page.locator('#financing .plot').bounding_box()
        page.mouse.move(box['x']+box['width']*.65,box['y']+80)
        for panel in ['financing','lending']:
            anchor=page.locator(f'#{panel} .lookback')
            selected=anchor.get_attribute('data-selected-date')
            assert anchor.get_attribute('data-anchor-date')==dates[dates.index(selected)-20]
            assert page.locator(f'#{panel} .lookback-label').is_visible()
        balances=pd.read_csv(root/'data/financing_accounts_daily.csv').set_index('date')
        def check_balances(target):
            for panel,column in [('financing','financing_balance_yi'),('lending','securities_lending_balance_yi')]:
                assert target.locator(f'#{panel} h2').inner_text().endswith('余额20日变化率')
                for selector in ['balance-current','balance-previous']:
                    date=target.locator(f'#{panel} .{selector} time').inner_text()
                    shown=target.locator(f'#{panel} .{selector} b').inner_text()
                    assert shown==f'{balances.loc[date,column]:,.2f} 亿元'
                assert target.locator(f'#{panel} .balance-current time').inner_text()==target.locator(f'#{panel} .reading time').inner_text()
                assert target.locator(f'#{panel} .balance-previous time').inner_text()==target.locator(f'#{panel} .lookback').get_attribute('data-anchor-date')
        check_balances(page)
        page.screenshot(path=str(tmp_path/'anchor-desktop.png'),full_page=True)
        # The previous 20 observations remain available outside the selected range.
        page.locator('#financing .plot').focus();page.keyboard.press('Home')
        assert '← T−20' in page.locator('#financing .lookback-label').text_content()
        assert not page.locator('#financing .lookback-line').is_visible()
        selected=page.locator('#financing .lookback').get_attribute('data-selected-date')
        assert page.locator('#financing .lookback').get_attribute('data-anchor-date')==dates[dates.index(selected)-20]
        page.screenshot(path=str(tmp_path/'anchor-outside.png'),full_page=True)
        page.locator('[data-range="all"]').click()
        page.locator('#financing .plot').focus();page.keyboard.press('Home')
        assert page.locator('#financing .lookback').get_attribute('data-anchor-date')==dates[0]
        phone=browser.new_page(viewport={'width':320,'height':850},is_mobile=True,has_touch=True)
        phone.goto((root/'index.html').as_uri());phone.wait_for_timeout(120)
        phone.locator('#lending .plot').scroll_into_view_if_needed()
        box=phone.locator('#lending .plot').bounding_box();phone.touchscreen.tap(box['x']+box['width']*.6,box['y']+100)
        assert phone.locator('#financing .lookback-label').is_visible()
        assert phone.locator('#lending .lookback').get_attribute('data-anchor-date')==phone.locator('#financing .lookback').get_attribute('data-anchor-date')
        assert phone.evaluate('document.documentElement.scrollWidth<=innerWidth')
        check_balances(phone)
        phone.screenshot(path=str(tmp_path/'anchor-mobile.png'),full_page=True)
        # A fresh range has no leftover hover shading.
        phone.locator('[data-range="1m"]').tap()
        assert not phone.locator('#financing .lookback').is_visible()
        browser.close()


def test_bias_chart_shared_range_and_selection(tmp_path):
    root=Path(__file__).resolve().parents[1]
    with sync_playwright() as w:
        browser=w.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':2000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((root/'index.html').as_uri());page.wait_for_timeout(200)
        assert page.locator('.bias-series').count()==7
        assert page.locator('[data-bias-value="1"]').inner_text()=='−25.23%'
        assert page.locator('[data-bias-value="6"]').inner_text()=='−14.15%'
        page.locator('#bias .plot').focus();page.keyboard.press('ArrowLeft')
        assert page.locator('#bias .bias-date').inner_text()==page.locator('#financing .reading time').inner_text()
        assert '2026-10-29' in page.locator('.bias-detail').inner_text()
        assert '收盘价' in page.locator('.bias-detail').inner_text()
        page.screenshot(path=str(tmp_path/'bias-desktop.png'),full_page=True)
        page.locator('[data-bias="1"]').uncheck(force=True)
        assert page.locator('[data-series="star"]').count()==0
        page.locator('[data-range="all"]').click()
        page.locator('#bias .plot').focus();page.keyboard.press('Home')
        assert page.locator('[data-bias-value="1"]').inner_text()=='—'
        page.screenshot(path=str(tmp_path/'bias-history.png'),full_page=True)
        phone=browser.new_page(viewport={'width':320,'height':850},is_mobile=True,has_touch=True)
        phone.on('pageerror',lambda e:errors.append(str(e)));phone.goto((root/'index.html').as_uri());phone.wait_for_timeout(200)
        phone.locator('#bias .plot').scroll_into_view_if_needed();bb=phone.locator('#bias .plot').bounding_box()
        phone.touchscreen.tap(bb['x']+bb['width']*.65,bb['y']+100)
        assert phone.locator('.bias-detail').inner_text()
        assert phone.evaluate('document.documentElement.scrollWidth<=innerWidth')
        phone.screenshot(path=str(tmp_path/'bias-mobile.png'),full_page=True)
        assert not errors,errors
        browser.close()


def test_etf_board_is_separate_from_original_chart(tmp_path):
    import json
    root=Path(__file__).resolve().parents[1]
    with sync_playwright() as w:
        browser=w.chromium.launch(headless=True)
        for width in [1440,360,320]:
            page=browser.new_page(viewport={'width':width,'height':1000},is_mobile=width<600,has_touch=width<600)
            page.route('https://*.gtimg.cn/**',lambda r:r.abort())
            page.goto((root/'index.html').as_uri())
            assert page.locator('[data-bias]').count()==7
            assert page.locator('#etf-monitor tbody tr').count()==12
            assert len(json.loads(page.locator('#etf-specs').text_content()))==12
            assert page.locator('#etf-monitor [data-code="159919"]').count()==1
            page.locator('#etf-monitor .etf-pause').click()
            assert page.locator('#etf-monitor .etf-pause').inner_text()=='继续刷新'
            page.locator('#etf-monitor [data-sort="code"]').click()
            assert page.locator('#etf-monitor tbody tr').first.get_attribute('data-code')=='588000'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path/f'etfs-{width}.png'),full_page=True)
            page.close()
        browser.close()
