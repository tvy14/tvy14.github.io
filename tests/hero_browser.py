"""Run with Playwright installed: python tests/hero_browser.py [public URL]."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import shutil
import sys
import threading
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
server = None
if len(sys.argv) > 1:
    url = sys.argv[1]
else:
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=shutil.which('google-chrome'), headless=True)
        for width, height in [(1440, 900), (390, 844), (360, 740)]:
            page = browser.new_page(viewport={'width': width, 'height': height})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
            assert response.status == 200
            preview = page.locator('#geomap-preview')
            preview.wait_for(state='visible')
            page.evaluate('document.fonts.ready')
            box = preview.bounding_box()
            assert box['y'] >= 52 and box['y'] + box['height'] <= height, box
            assert page.locator('#geomap-heading').inner_text() == 'Try our MiniRAN Geo Mapper!'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'
            frame = preview.element_handle().content_frame()
            frame.wait_for_function("document.querySelectorAll('.leaflet-tile-loaded').length > 0 && Number(document.getElementById('kpi-bs').textContent) > 0")
            assert not frame.locator('#sidebar').is_visible()
            map_box = frame.locator('#map').bounding_box()
            assert abs(map_box['width'] - box['width']) <= 2, (map_box, box)
            frame.locator('.leaflet-control-zoom-in').click()
            assert page.locator('.geomap-launch').get_attribute('href') == 'https://tvy14.github.io/miniran-geomap/'
            if width == 1440:
                with page.expect_popup() as popup_info:
                    page.locator('.geomap-launch').click()
                popup = popup_info.value
                popup.wait_for_load_state('domcontentloaded')
                assert popup.url == 'https://tvy14.github.io/miniran-geomap/'
                assert popup.locator('#sidebar').is_visible()
                popup.close()
            assert not page.locator('#galton').is_visible()
            summary = page.locator('#galton-game summary')
            summary.click()
            assert page.locator('#galton').is_visible()
            canvas = page.locator('#galton')
            before = canvas.evaluate('(c) => c.toDataURL()')
            page.wait_for_timeout(300)
            assert canvas.evaluate('(c) => c.toDataURL()') != before, 'Galton animation did not start'
            canvas.click()
            summary.click()
            assert not canvas.is_visible()
            summary.click()
            assert canvas.is_visible()
            assert not errors, errors
            print(json.dumps({'viewport': [width, height], 'preview_above_fold': True, 'map_loaded': True, 'galton_toggle_and_animation': 'passed', 'javascript_errors': errors}))
            page.close()
        browser.close()
finally:
    if server:
        server.shutdown()
        server.server_close()
