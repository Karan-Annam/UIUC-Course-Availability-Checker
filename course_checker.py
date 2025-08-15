# pip install playwright
# playwright install chromium

import time, re
import random
import requests
from playwright.sync_api import sync_playwright

PROFILE_DIR   = "reg_profile"
HEADLESS      = False          # keep browser visible 

WEBHOOK_URL = "https://discord.com/api/webhooks/1405772690039771137/MGwG04R3c98ay2uFBoIL1JwHkgoodNnYXYFQkrZLF1yUBfuIhLZSXBdvRPY8ekLLwkl3"  

SUBJECT = "ECE"
COURSE  = "210"
DELAY_TIME = 10  
DELAY_MARGIN = 5 

TARGET_CRN = "36706"   # course crn


FIND_TOKENS = [
    re.compile(r"Find Classes", re.I),
    re.compile(r"Enter CRNs", re.I),
    re.compile(r"Schedule and Options", re.I),
    re.compile(r"Register for Classes", re.I),  
]

def send_to_discord(message: str):
    """Send a text message to the configured Discord webhook."""
    try:
        payload = {"content": message}
        resp = requests.post(WEBHOOK_URL, json=payload)
        if resp.status_code != 204:
            print(f"[WARN] Discord webhook returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[WARN] Could not send to Discord: {e}")

def launch():
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=HEADLESS,
        args=["--disable-blink-features=AutomationControlled"],
    )
    return pw, ctx, ctx.new_page()

def frame_has_registration_ui(frame) -> bool:
    """Return True if this frame looks like the registration page."""
    try:
        if frame.get_by_role("tab", name=re.compile(r"Find Classes", re.I)).count():
            return True
    except Exception:
        pass
    try:
        for pat in FIND_TOKENS:
            if frame.get_by_text(pat, exact=False).count():
                return True
    except Exception:
        pass
    return False

def wait_until_on_registration(page):
    print(">>> Navigate manually to the **Register for Classes** page; I'll detect it.")
    while True:
        if frame_has_registration_ui(page):
            print(f"[INFO] Detected in main page. URL: {page.url}")
            return page
        for fr in page.frames:
            if frame_has_registration_ui(fr):
                print(f"[INFO] Detected in iframe. Frame URL: {fr.url} | Outer URL: {page.url}")
                return fr
        time.sleep(0.3)

def fill_ece_210(ctx):
    import re
    # Ensure we’re on Find Classes
    try:
        ctx.get_by_role("tab", name=re.compile(r"Find Classes", re.I)).click(timeout=2500)
    except Exception:
        pass

    # locate the Subject combobox input
    subj_input = None
    for sel in [
        "//label[normalize-space()='Subject']/following::div[@role='combobox']//input[1]",
        "//label[contains(.,'Subject')]/following::input[1]",
        "div[role='combobox'] input",
        "input[aria-label='Subject']",
        "input[placeholder='Subject']",
    ]:
        l = ctx.locator(sel).first
        if l.count():
            subj_input = l
            break
    if subj_input is None:
        subj_input = ctx.get_by_label(re.compile(r"Subject", re.I)).first  # last resort

    # open dropdown & try direct option click 
    subj_input.click()
    subj_input.fill("Electrical and Computer Engr")
    ctx.wait_for_timeout(250)

    # common option texts: "Electrical and Computer Engr" OR "Electrical & Computer Engr"
    opt_regex = re.compile(r"Electrical\s*(?:and|&)\s*Computer\s*Engr", re.I)
    options = ctx.locator("ul[role='listbox'] li[role='option']")
    ece_opt = options.filter(has_text=opt_regex).first

    if ece_opt.count():
        try:
            ece_opt.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass
        ece_opt.click()
    else:
        # fallback 1: click the first visible option that contains 'Electrical'
        any_elec = options.filter(has_text=re.compile(r"Electrical", re.I)).first
        if any_elec.count():
            any_elec.click()
        else:
            # fallback 2: type ECE and use keyboard to select
            subj_input.fill("ECE")
            ctx.wait_for_timeout(250)
            # Try up to 10 ArrowDowns then Enter
            for _ in range(10):
                subj_input.press("ArrowDown")
                ctx.wait_for_timeout(120)
            subj_input.press("Enter")

    # Course Number = 210
    try:
        cn = ctx.get_by_label(re.compile(r"Course Number", re.I)).first
        cn.click(); cn.fill("210")
    except Exception:
        for css in ("input[aria-label='Course Number']",
                    "input[placeholder='Course Number']",
                    "input[name='courseNumber']"):
            el = ctx.locator(css).first
            if el.count():
                el.click(); el.fill("210")
                break

    # Click the real Search button
    try:
        if ctx.locator("#search-go").count():
            ctx.locator("#search-go").click(timeout=4000)
        else:
            ctx.get_by_role("button", name="Search").click(timeout=4000)  # exact match
    except Exception as e:
        print(f"[WARN] Couldn't click Search automatically: {e}  (You can click it manually.)")

    print("[INFO] Subject 'Electrical and Computer Engr' selected, Course=210 set, Search clicked.")

#
def go_to_page_2(ctx):
    try:
        
        pager_next = ctx.locator("button[title='Next'], button.paging-control.next").first
        pager_next.wait_for(timeout=5000)
        pager_next.click()
        print("[INFO] Moved to page 2.")
    except Exception as e:
        print(f"[WARN] Could not go to page 2 automatically: {e}")



def report_seats_for_crn(ctx, crn: str):
    """
    Find the row that contains the CRN, then extract "x of y seats"
    from that row or the immediate detail row after it.
    """
    try:
        # 1) Results table/grid
        table = ctx.locator("table, div[role='table']").first
        table.wait_for(state="visible", timeout=6000)

        # 2) Find the CRN cell (td or role=gridcell)
        crn_re = re.compile(rf"\b{re.escape(crn)}\b")
        cell = table.locator("td, div[role='gridcell']").filter(has_text=crn_re).first
        if cell.count() == 0:
            msg = f"[INFO] CRN {crn}: not found on this page."
            print(msg)
            send_to_discord(msg)
            return

        # 3) Walk up to the row (try <tr> first, then role=row)
        row = cell.locator("xpath=ancestor::tr").first
        if row.count() == 0:
            row = cell.locator("xpath=ancestor::div[@role='row']").first

        # 4) Seats text may be in this row or its next sibling detail row
        row_text = row.inner_text(timeout=3000)
        next_text = ""
        try:
            next_text = row.locator("xpath=following-sibling::*[1]").inner_text(timeout=800)
        except Exception:
            pass

        text = row_text + " " + next_text

        # 5) Parse "x of y seats"
        m = re.search(r"(\d+)\s*of\s*(\d+)\s*seats", text, re.I)
        if not m:
            msg = f"[INFO] CRN {crn}: seats text not found."
            print(msg)
            send_to_discord(msg)
            return

        x, y = int(m.group(1)), int(m.group(2))
        status = "OPEN" if x > 0 else "FULL"
        msg = f"[SEATS] CRN {crn}: {x} of {y} seats — {status}"
        print(msg)
        send_to_discord(msg)


    except Exception as e:
        msg = f"[ERROR] Failed to report seats for CRN {crn}: {e}"
        print(msg)
        send_to_discord(msg)




# in main(), repeat: fill+search -> go page2 -> wait 10s -> reload
def main():
    pw, ctx, page = launch()
    try:
        # Wait for you to navigate to the Register for Classes page
        reg_ctx = wait_until_on_registration(page)

        # Repeat forever: fill → click Search → go to page 2 → wait 10s → reload → repeat
        while True:
            try:
                reg_ctx = wait_until_on_registration(page)  # re-detect context each cycle
                fill_ece_210(reg_ctx)
                # small pause so results render before paging
                reg_ctx.wait_for_timeout(800)
                go_to_page_2(reg_ctx)
                reg_ctx.wait_for_timeout(2000)
                report_seats_for_crn(reg_ctx, TARGET_CRN)
            except Exception as e:
                print(f"[WARN] Cycle error: {e}")

            delay = random.uniform(DELAY_TIME - DELAY_MARGIN, DELAY_TIME + DELAY_MARGIN)
            print(f"[INFO] Waiting {delay:.1f} seconds before refresh...")
            time.sleep(delay)
            page.reload(wait_until="domcontentloaded")
    finally:
        try:
            ctx.close()
        except:
            pass
        pw.stop()

if __name__ == "__main__":
    main()
