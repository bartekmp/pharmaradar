"""
WebDriver utilities for medicine scraping.

Contains helper classes and functions for WebDriver operations.
"""

import logging
import os
import shutil
import subprocess
import time
from typing import Any, Callable, List, Optional, TypeVar

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

T = TypeVar("T")


class WebDriverManager:
    """Manages WebDriver instances with proper cleanup and configuration."""

    def __init__(self, headless: bool = True, timeout: int = 15, log: logging.Logger = logging.getLogger()):
        self.headless = headless
        self.timeout = timeout
        self.driver: Optional[webdriver.Remote] = None
        self.log = log

    def __enter__(self) -> "WebDriverManager":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the WebDriver if it's open with cleanup."""
        if self.driver:
            try:
                # Close all windows
                for handle in self.driver.window_handles:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                self.driver.quit()
            except Exception as e:
                self.log.warning(f"Error closing WebDriver: {e}")
                WebDriverUtils.cleanup_hanging_processes()
            finally:
                self.driver = None

    def get_driver(self) -> webdriver.Remote:
        """Get a configured WebDriver instance with retries and automatic driver installation."""
        if self.driver:
            try:
                # Test if driver is still responsive
                self.driver.current_url
                return self.driver
            except (WebDriverException, Exception):
                self.log.warning("Existing driver not responsive, creating new one")
                self.close()

        # Clean up any existing processes/data before starting
        WebDriverUtils.cleanup_hanging_processes()

        # Start virtual display for container environments
        WebDriverUtils.start_virtual_display()

        # Try Chrome with system driver
        chrome_error = None
        try:
            chrome_options = WebDriverUtils.get_chrome_options(self.headless)

            # Use system ChromeDriver (Alpine/Docker)
            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
            if os.path.exists(chromedriver_path):
                service = ChromeService(chromedriver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Try default Chrome without explicit driver path
                self.driver = webdriver.Chrome(options=chrome_options)

            # Test the driver
            self.driver.get("data:,")  # Simple test page
            return self.driver
        except Exception as e:
            chrome_error = str(e)
            self.log.warning(f"Chrome WebDriver failed: {e}")
            if self.driver:
                self.driver.quit()
                self.driver = None

        # Chrome failed - provide error message
        error_msg = f"No WebDriver available. Chrome WebDriver failed to initialize.\n\nChrome Error: {chrome_error}"
        self.log.error(error_msg)
        raise RuntimeError(error_msg)


class WebDriverUtils:
    """Utility functions for WebDriver operations."""

    @staticmethod
    def cleanup_hanging_processes() -> None:
        """Clean up any hanging Chrome/ChromeDriver processes and temporary data."""
        try:
            # Clean up processes
            subprocess.run(["pkill", "-f", "chrome.*--headless"], stderr=subprocess.DEVNULL, check=False)
            subprocess.run(["pkill", "-f", "chromedriver"], stderr=subprocess.DEVNULL, check=False)
            subprocess.run(["pkill", "-f", "chromium"], stderr=subprocess.DEVNULL, check=False)
            subprocess.run(["pkill", "-f", "Xvfb"], stderr=subprocess.DEVNULL, check=False)

            # Clean up temporary Chrome data directories

            temp_dirs = [
                "/tmp/chrome-user-data",
                "/tmp/chrome-data",
                "/tmp/chrome-cache",
                "/dev/shm/chrome-user-data",
                "/dev/shm/chrome-data",
                "/dev/shm/chrome-cache",
                "/dev/shm/chrome-crashes",
            ]
            for temp_dir in temp_dirs:
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

            time.sleep(1)
        except Exception as e:
            return

    @staticmethod
    def start_virtual_display() -> None:
        """Start virtual display for containerized environments."""
        try:
            # Get DISPLAY variable
            virtual_display = os.environ.get("DISPLAY", ":99")
            # Check if Xvfb is already running
            result = subprocess.run(["pgrep", "-f", f"Xvfb.*{virtual_display}"], stderr=subprocess.DEVNULL, check=False)
            if result.returncode != 0:  # Xvfb not running
                # Start Xvfb in background
                subprocess.Popen(
                    ["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-nolisten", "tcp", "-dpi", "96"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(2)  # Give Xvfb time to start
        except Exception as e:
            return

    @staticmethod
    def get_chrome_options(headless: bool = True) -> ChromeOptions:
        """Get configured Chrome options."""
        chrome_options = ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")

        # Check if we're in Alpine/Docker and set binary path
        chrome_binary = os.environ.get("CHROME_BIN")
        if chrome_binary and os.path.exists(chrome_binary):
            chrome_options.binary_location = chrome_binary
        elif os.path.exists("/usr/bin/chromium-browser"):
            # Alpine Linux path
            chrome_options.binary_location = "/usr/bin/chromium-browser"
        elif os.path.exists("/usr/bin/chromium"):
            # Some other Linux distributions
            chrome_options.binary_location = "/usr/bin/chromium"

        # Essential arguments for containerized environments
        essential_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI,BlinkGenPropertyTrees",
            "--disable-ipc-flooding-protection",
            "--disable-features=VizDisplayCompositor",
            "--disable-web-security",
            "--disable-features=RendererCodeIntegrity",
            "--disable-blink-features=AutomationControlled",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-setuid-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-client-side-phishing-detection",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-domain-reliability",
            "--disable-component-update",
            "--disable-background-downloads",
            "--disable-add-to-shelf",
            "--disable-autofill",
            "--disable-infobars",
            "--window-size=1920,1080",
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--memory-pressure-off",
            "--max_old_space_size=4096",
            "--disable-logging",
            "--disable-login-animations",
            "--disable-motion-blur",
            "--disable-smooth-scrolling",
            "--force-color-profile=srgb",
            # Additional options to fix preference writing issues
            "--disable-preferences-service",
            "--disable-background-mode",
            "--disable-features=VizDisplayCompositor",
            "--disable-features=ChromeWhatsNewUI",
            "--disable-features=RendererCodeIntegrity",
            "--single-process",
            "--no-zygote",
            "--disable-features=MediaRouter",
            "--disable-features=Translate",
            "--disable-features=OptimizationHints",
            "--disable-search-engine-choice-screen",
            "--disable-cloud-management-enrollment",
            # Try to avoid file system writes entirely
            "--disable-local-storage",
            "--disable-databases",
            "--disable-shared-workers",
            "--disable-file-system",
            "--incognito",
            # Don't specify user-data-dir - let Chrome use default temp location
        ]

        for arg in essential_args:
            chrome_options.add_argument(arg)

        # Add preferences to minimize file system usage
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
            },
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2,
            "profile.password_manager_enabled": False,
            "credentials_enable_service": False,
            "profile.password_manager_leak_detection": False,
            "autofill.profile_enabled": False,
            "autofill.credit_card_enabled": False,
            "translate.enabled": False,
            "plugins.always_open_pdf_externally": True,
            "download.default_directory": "/dev/shm",
            "download.prompt_for_download": False,
            "safebrowsing.enabled": False,
            "safebrowsing.disable_download_protection": True,
            "safebrowsing.disable_extension_blacklist": True,
        }
        chrome_options.add_experimental_option("prefs", prefs)

        return chrome_options

    @staticmethod
    def get_firefox_options(headless: bool = True) -> FirefoxOptions:
        """Get configured Firefox options."""
        firefox_options = FirefoxOptions()
        if headless:
            firefox_options.add_argument("--headless")
        return firefox_options

    @staticmethod
    def safe_execute(operation: Callable[[], T], error_message: str, default_return: Optional[T] = None) -> Optional[T]:
        """Safely execute an operation with error handling."""
        try:
            return operation()
        except Exception as e:
            return default_return

    @staticmethod
    def find_element_with_fallbacks(
        driver: webdriver.Remote, selectors: List[str], description: str = "element"
    ) -> Optional[WebElement]:
        """Find element using multiple selectors as fallback."""
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    return element
            except Exception:
                continue
        return None

    @staticmethod
    def safe_click(driver: webdriver.Remote, element: WebElement, description: str = "element") -> bool:
        """Safely click an element using multiple strategies."""
        try:
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(0.5)

            # Try regular click first
            element.click()
            return True
        except Exception:
            try:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", element)
                return True
            except Exception as e:
                return False

    @staticmethod
    def wait_for_page_load(driver: webdriver.Remote, timeout: int = 10) -> bool:
        """Wait for page to load completely."""
        try:
            WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")
            return True
        except Exception as e:
            return False
