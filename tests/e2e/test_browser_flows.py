from pathlib import Path
import json

import pytest


AXE_SOURCE = Path(__file__).parents[2] / "app/static/vendor/axe.min.js"


def test_turkish_font_families_are_loaded(page, live_server_url):
    page.goto(f"{live_server_url}/login")
    page.wait_for_function("document.fonts.status === 'loaded'")

    result = page.evaluate("""() => {
        const heading = document.querySelector('.login-form h2');
        const body = document.querySelector('.login-form > p');
        const loadedFamilies = [...document.fonts]
            .filter(face => face.status === 'loaded')
            .map(face => face.family.replaceAll('"', ''));
        return {
            headingFamily: getComputedStyle(heading).fontFamily,
            bodyFamily: getComputedStyle(body).fontFamily,
            familjenLoaded: loadedFamilies.includes('Familjen Grotesk'),
            manropeLoaded: loadedFamilies.includes('Manrope'),
        };
    }""")

    assert result["headingFamily"].startswith('"Familjen Grotesk"')
    assert result["bodyFamily"].startswith('Manrope') or result["bodyFamily"].startswith('"Manrope"')
    assert result["familjenLoaded"] is True
    assert result["manropeLoaded"] is True


@pytest.mark.parametrize("viewport", [{"width": 400, "height": 765}, {"width": 1280, "height": 900}])
def test_authenticated_shell_has_no_serious_accessibility_violations(authenticated_page, viewport):
    page = authenticated_page
    page.set_viewport_size(viewport)
    page.reload()
    page.add_script_tag(content=AXE_SOURCE.read_text())
    result = page.evaluate("async () => await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}})")
    serious = [v for v in result["violations"] if v["impact"] in {"serious", "critical"}]
    assert serious == [], json.dumps(serious, ensure_ascii=False, indent=2)


def test_primary_navigation_and_security_headers(authenticated_page, live_server_url):
    page = authenticated_page
    response = page.goto(f"{live_server_url}/parties/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert response.headers["x-request-id"]
    assert page.get_by_role("heading", name="Kişiler").is_visible()


def test_person_invoice_and_payment_critical_flow(authenticated_page, live_server_url):
    page = authenticated_page

    page.goto(f"{live_server_url}/parties/add")
    page.locator("#first_name").fill("Tarayıcı")
    page.locator("#last_name").fill("Hastası")
    page.locator("#phone").fill("5554443322")
    page.get_by_role("button", name="Kaydet").click()
    page.wait_for_url(f"{live_server_url}/parties/*")
    party_id = page.url.rstrip("/").split("/")[-1]

    page.goto(f"{live_server_url}/invoices/add")
    page.locator("#party-select").select_option(value=party_id, force=True)
    page.locator("#add-custom-btn").click()
    page.locator("#item-description").fill("E2E özel hizmet")
    page.locator("#item-unit-price-eur").fill("100")
    page.locator("#item-form").get_by_role("button", name="Ekle").click()
    page.get_by_role("button", name="Fatura Oluştur").click()
    page.wait_for_url(f"{live_server_url}/invoices/*")
    invoice_id = page.url.rstrip("/").split("/")[-1]

    page.goto(f"{live_server_url}/payments/add?invoice_id={invoice_id}")
    page.locator("#amount-eur").fill("100")
    page.get_by_role("button", name="Kaydet").click()
    page.wait_for_url(f"{live_server_url}/payments/")
    assert page.get_by_text("€100.00").first.is_visible()
