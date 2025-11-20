#!/usr/bin/env python3
"""
RateMySite scraping logic with debugging - Railway/Docker compatible
"""

import json
import re
import time
import traceback
import os
import subprocess
import shutil
from typing import Dict, List, Optional, Generator

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

RATEMYSITE_URL = "https://www.ratemysite.xyz/"
DEFAULT_TIMEOUT = 45

def _find_chrome_executable():
    """Find Chrome executable in different environments"""
    possible_names = [
        'google-chrome',
        'google-chrome-stable', 
        'chromium',
        'chromium-browser',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser'
    ]
    
    for name in possible_names:
        path = shutil.which(name)
        if path:
            return path
            
    # Check common paths manually
    common_paths = [
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/opt/google/chrome/google-chrome'
    ]
    
    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    return None

def _find_chromedriver():
    """Find ChromeDriver executable"""
    # Try to find chromedriver
    driver_path = shutil.which('chromedriver')
    if driver_path:
        return driver_path
        
    # Common paths for chromedriver
    common_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver'
    ]
    
    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    return None

def _make_driver(headless: bool = True) -> Optional[webdriver.Chrome]:
    """Create Chrome WebDriver with Railway/Docker compatibility"""
    chrome_opts = Options()
    
    # Find Chrome executable
    chrome_binary = _find_chrome_executable()
    if chrome_binary:
        chrome_opts.binary_location = chrome_binary
    
    # Essential options for containerized environments
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--disable-extensions")
    chrome_opts.add_argument("--disable-setuid-sandbox")
    chrome_opts.add_argument("--disable-web-security")
    chrome_opts.add_argument("--disable-features=VizDisplayCompositor")
    chrome_opts.add_argument("--window-size=1920,1080")
    chrome_opts.add_argument("--remote-debugging-port=9222")
    chrome_opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    if headless:
        chrome_opts.add_argument("--headless")
    
    # Try to find chromedriver
    driver_path = _find_chromedriver()
    
    try:
        if driver_path:
            # Use found chromedriver
            service = Service(driver_path)
            return webdriver.Chrome(service=service, options=chrome_opts)
        else:
            # Try to use webdriver-manager as fallback
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                return webdriver.Chrome(service=service, options=chrome_opts)
            except Exception as e:
                print(f"ChromeDriverManager failed: {e}")
                # Try without service (let selenium find chromedriver)
                return webdriver.Chrome(options=chrome_opts)
                
    except WebDriverException as e:
        print(f"Failed to create Chrome driver: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error creating driver: {e}")
        return None

def _find_first(driver, xpaths: List[str]) -> Optional[object]:
    """Find first element matching any of the provided XPaths"""
    for xp in xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            if el and el.is_displayed():
                return el
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return None

def _click_best_button(driver) -> bool:
    """Try to find and click the best submit button"""
    xpaths = [
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'analy')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'rate')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'submit')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'generate')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'get report')]",
        "//button[@type='submit']",
        "//button",
        "//div[@role='button']",
    ]
    btn = _find_first(driver, xpaths)
    if not btn:
        return False
    try:
        if btn.is_enabled():
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            return True
    except Exception:
        pass
    return False

def _maybe_close_cookie_banner(driver):
    """Attempt to close cookie banners"""
    candidates = [
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'agree')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'allow')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ok')]",
        "//*[contains(@class,'cookie')]//button",
        "//*[@id='onetrust-accept-btn-handler']",
    ]
    try:
        btn = _find_first(driver, candidates)
        if btn:
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.3)
    except Exception:
        pass

def _collect_result_text(driver) -> str:
    """Extract result text from the page"""
    containers = driver.find_elements(
        By.XPATH,
        "//*[contains(@class,'result') or contains(@class,'report') or contains(@class,'output') or @role='article']",
    )
    texts = [c.text.strip() for c in containers if c.text and c.text.strip()]
    if texts:
        return "\n\n".join(texts).strip()
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        return (body.text or "").strip()
    except Exception:
        return ""

def _wait_for_content_growth(driver, wait: WebDriverWait, min_growth: int = 80) -> None:
    """Wait for content to grow (indicating dynamic loading)"""
    try:
        initial_len = len(driver.find_element(By.TAG_NAME, "body").text)
    except Exception:
        initial_len = 0
    try:
        wait.until(lambda d: len(d.find_element(By.TAG_NAME, "body").text) > initial_len + min_growth)
    except TimeoutException:
        pass

def _analyze_one_with_debugging(target_url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, List[str]]:
    """Analyze a single URL with detailed debugging"""
    debug_log = []
    
    try:
        debug_log.append("Creating Chrome driver...")
        driver = _make_driver(headless=True)
        
        if not driver:
            debug_log.append("ERROR: Failed to create Chrome driver - Chrome may not be installed")
            return "", debug_log
            
        wait = WebDriverWait(driver, timeout)
        
        debug_log.append(f"Navigating to {RATEMYSITE_URL}")
        driver.get(RATEMYSITE_URL)
        
        debug_log.append("Checking for cookie banners...")
        _maybe_close_cookie_banner(driver)

        input_xpaths = [
            "//input[@type='url']",
            "//input[contains(@placeholder,'https')]",
            "//input[contains(@placeholder,'http')]",
            "//input[contains(@placeholder,'Enter') or contains(@placeholder,'enter')]",
            "//input",
            "//textarea",
        ]
        
        debug_log.append("Looking for input field...")
        try:
            input_el = wait.until(EC.presence_of_element_located((By.XPATH, "|".join(input_xpaths))))
            debug_log.append("Found input field using wait condition")
        except Exception as e:
            debug_log.append(f"Wait condition failed: {e}")
            input_el = _find_first(driver, input_xpaths)
            if input_el:
                debug_log.append("Found input field using fallback method")
            
        if not input_el:
            debug_log.append("ERROR: Could not locate input field!")
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
                debug_log.append(f"Body text: {body_text}")
            except Exception as e:
                debug_log.append(f"Could not get body text: {e}")
            return "", debug_log

        debug_log.append(f"Entering URL: {target_url}")
        try:
            input_el.clear()
        except Exception:
            pass
        input_el.send_keys(target_url)
        time.sleep(0.3)

        debug_log.append("Attempting to submit...")
        clicked = _click_best_button(driver)
        if clicked:
            debug_log.append("Successfully clicked submit button")
        else:
            debug_log.append("Button click failed, trying Enter key...")
            try:
                input_el.send_keys("\n")
                debug_log.append("Sent Enter key")
            except Exception as e:
                debug_log.append(f"Enter key failed: {e}")

        debug_log.append("Waiting for results to load...")
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(@class,'result') or contains(@class,'report') or @role='article']")
                )
            )
            debug_log.append("Found result container")
        except TimeoutException:
            debug_log.append("No result container found, waiting for content growth...")
            _wait_for_content_growth(driver, wait, min_growth=120)
            debug_log.append("Finished waiting for content growth")

        time.sleep(1.0)
        debug_log.append("Extracting result text...")
        result_text = _collect_result_text(driver)
        debug_log.append(f"Extracted {len(result_text)} characters of result text")
        
        if not result_text:
            debug_log.append("No result text found! Getting page debug info...")
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text
                debug_log.append(f"Full page text length: {len(page_text)}")
                debug_log.append(f"Page text preview: {page_text[:800]}")
            except Exception as e:
                debug_log.append(f"Could not get page text: {e}")
        
        return result_text, debug_log

    except Exception as e:
        debug_log.append(f"ERROR in analysis: {e}")
        debug_log.append(f"Traceback: {traceback.format_exc()}")
        return "", debug_log
    finally:
        try:
            if 'driver' in locals() and driver:
                debug_log.append("Closing driver...")
                driver.quit()
        except Exception as e:
            debug_log.append(f"Error closing driver: {e}")

def _grab_block(text: str, labels: List[str], multiline=True) -> str:
    """Extract a block of text based on labels"""
    for lab in labels:
        if multiline:
            m = re.search(rf"{lab}\s*[:\-]?\s*(.+?)(?:\n\s*\n|\n[A-Z][^\n]{{0,60}}:\s|$)", text, flags=re.I | re.S)
        else:
            m = re.search(rf"{lab}\s*[:\-]?\s*([^\n]+)", text, flags=re.I)
        if m:
            return m.group(1).strip()
    return "-"

def _grab_score(text: str, labels: List[str]) -> str:
    """Extract a numeric score based on labels"""
    for lab in labels:
        m = re.search(rf"{lab}\s*[:\-]?\s*(\d{{1,3}})", text, flags=re.I)
        if m:
            return m.group(1)
    return "-"

def _parse_fields(url: str, raw: str) -> Dict[str, str]:
    """Parse the raw text into structured fields"""
    return {
        "Company": _grab_block(raw, ["Company", "Site Name", "Website Name"], multiline=False),
        "URL": url,
        "Overall Score": _grab_score(raw, ["Overall Score", "Score", "Total Score"]),
        "Description of Website": _grab_block(raw, ["Description of Website", "Description", "Site Description"]),
        "Consumer Score": _grab_score(raw, ["Consumer Score", "Customer Score", "End-user Score"]),
        "Developer Score": _grab_score(raw, ["Developer Score", "Engineer Score", "Dev Score"]),
        "Investor Score": _grab_score(raw, ["Investor Score"]),
        "Clarity Score": _grab_score(raw, ["Clarity Score", "Readability Score"]),
        "Visual Design Score": _grab_score(raw, ["Visual Design Score", "Design Score"]),
        "UX Score": _grab_score(raw, ["UX Score", "Usability Score"]),
        "Trust Score": _grab_score(raw, ["Trust Score", "Credibility Score"]),
        "Value Prop Score": _grab_score(raw, ["Value Prop Score", "Value Proposition Score"]),
        "_raw": raw,
    }

def sse(event: str, data: dict) -> str:
    """Format Server-Sent Event"""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def stream_analysis(urls: List[str]) -> Generator[str, None, None]:
    """Stream analysis results for multiple URLs"""
    total = len(urls)
    
    TABLE_ROWS = [
        ("Company", "Company"),
        ("URL", "URL"),
        ("Overall Score", "Overall Score"),
        ("Description of Website", "Description of Website"),
        ("Consumer Score", "Audience Perspective → Consumer"),
        ("Developer Score", "Audience Perspective → Developer"),
        ("Investor Score", "Audience Perspective → Investor"),
        ("Clarity Score", "Technical Criteria → Clarity"),
        ("Visual Design Score", "Technical Criteria → Visual Design"),
        ("UX Score", "Technical Criteria → UX"),
        ("Trust Score", "Technical Criteria → Trust"),
        ("Value Prop Score", "Value Proposition"),
    ]
    
    yield sse("init", {"total": total, "rows": TABLE_ROWS})

    for idx, raw in enumerate(urls, start=1):
        url = raw if raw.startswith(("http://", "https://")) else "https://" + raw
        step_total = 5
        cur = 0

        print(f"[{idx}/{total}] Start {url}")
        yield sse("start_url", {"index": idx, "url": url})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Creating fresh browser", "p": cur, "of": step_total})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Submitting to RateMySite", "p": cur, "of": step_total})
        
        raw_text, debug_messages = _analyze_one_with_debugging(url, timeout=DEFAULT_TIMEOUT)
        
        for msg in debug_messages:
            yield sse("debug", {"index": idx, "message": msg})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Parsing output", "p": cur, "of": step_total})
        
        if raw_text:
            data = _parse_fields(url, raw_text)
            yield sse("result", {"index": idx, "url": url, "data": data})
        else:
            yield sse("result", {"index": idx, "url": url, "error": "No results found - check debug log"})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Done", "p": cur, "of": step_total})
        print(f"[{idx}/{total}] Done {url}")

    yield sse("done", {"ok": True})
