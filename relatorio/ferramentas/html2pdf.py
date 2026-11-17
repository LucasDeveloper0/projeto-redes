import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
pdf = Path(sys.argv[2]).resolve()
with sync_playwright() as p:
    nav = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    pg = nav.new_page()
    pg.goto(html.as_uri(), wait_until="load")
    pg.wait_for_timeout(800)
    pg.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True,
           display_header_footer=True, header_template="<span></span>",
           footer_template='<div style="width:100%;font-size:8px;text-align:center;color:#555;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
           margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"})
    nav.close()
print("pdf:", pdf)
