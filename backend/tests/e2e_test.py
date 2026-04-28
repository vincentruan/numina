#!/usr/bin/env python3
"""E2E tests for Numina application - verifies all pages render correctly."""
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 375, 'height': 812})
        page = context.new_page()

        results = []

        # Public pages - should render
        public_pages = [
            ('/numina/login', '.login-page', 'Login'),
            ('/numina/register', '.register-page', 'Register'),
        ]

        # Protected pages - should redirect to login
        protected_pages = [
            ('/numina/', 'Dashboard'),
            ('/numina/wishes', 'Wishes'),
            ('/numina/settings', 'Settings'),
            ('/numina/stats', 'Data Stats'),
            ('/numina/family', 'Family'),
            ('/numina/assets/new', 'Asset Form'),
        ]

        for path, selector, name in public_pages:
            try:
                page.goto(f'http://localhost:5173{path}', timeout=15000)
                page.wait_for_load_state('networkidle')
                page.wait_for_selector(selector, timeout=5000)
                results.append(f"✅ {name}: PASS (renders)")
            except Exception as e:
                results.append(f"❌ {name}: FAIL - {str(e)[:40]}")

        for path, name in protected_pages:
            try:
                page.goto(f'http://localhost:5173{path}', timeout=15000)
                page.wait_for_load_state('networkidle')
                # Should redirect to login
                current_url = page.url
                if 'login' in current_url:
                    results.append(f"✅ {name}: PASS (auth guard)")
                else:
                    results.append(f"⚠️ {name}: No redirect to: {current_url[:40]}")
            except Exception as e:
                results.append(f"❌ {name}: FAIL - {str(e)[:40]}")

        browser.close()

        print("\n" + "="*50)
        print("E2E Test Results")
        print("="*50)
        for r in results:
            print(r)

        passed = len([r for r in results if 'PASS' in r])
        print(f"\n📊 Total: {passed}/{len(results)} tests passed")

        return passed == len(results)

if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)