from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto("http://localhost:8000")

    # Upload a receipt
    page.set_input_files('input[name="receipt_image"]', 'IMG_6839.HEIC')
    page.locator('input[name="uploader_name"]').fill("Jules")
    page.locator('button[type="submit"]').click()

    # Wait for the modal to appear
    modal = page.locator('[data-component="add-tip-modal"]')
    expect(modal).to_be_visible()
    page.screenshot(path="jules-scratch/verification/01_modal_initial_state.png")

    # Click 15% button
    modal.locator('[data-action="set-tip-percentage"][data-value="15"]').click()
    page.screenshot(path="jules-scratch/verification/02_modal_15_percent.png")

    # Change to dollar amount and enter a value
    modal.locator('[data-action="set-tip-type"][data-type="dollar"]').click()
    modal.locator('[data-input="tip-value"]').fill("12.34")
    page.screenshot(path="jules-scratch/verification/03_modal_dollar_amount.png")

    # Apply the tip
    modal.locator('[data-action="apply-tip"]').click()
    expect(modal).not_to_be_visible()

    # Take a screenshot of the edit page with the updated tip
    page.screenshot(path="jules-scratch/verification/04_edit_page_updated_tip.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
