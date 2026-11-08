"""One language setting drives the voice and the whole interface.

These tests pin the contract the README makes:

* every ``static/i18n/<code>.json`` file carries every English key, so a
  language can never render a raw key or silently fall back;
* placeholders survive translation, so a string cannot lose ``{name}``;
* the removed interface-only dropdown and its storage key are gone, and the
  loader runs before ``app.js``;
* every ``t("…")`` / ``data-i18n`` key used by the frontend exists in English;
* switching language really changes the visible text;
* server texts follow the request language and fall back to English (never to
  Hinglish) when a table has no entry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from messages import tr

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "static" / "i18n"

CODES = ["en", "hi", "hing", "mr", "bn", "gu", "kn", "ml", "pa", "ta", "te"]
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def load(code: str) -> dict[str, str]:
    return json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))


def test_key_parity_with_english():
    english = load("en")
    for code in CODES:
        data = load(code)
        missing = sorted(set(english) - set(data))
        assert not missing, f"{code}.json is missing {missing}"


def test_placeholders_survive_translation():
    english = load("en")
    for code in CODES:
        data = load(code)
        for key, value in data.items():
            assert set(PLACEHOLDER.findall(value)) == set(
                PLACEHOLDER.findall(english[key])
            ), f"{code}.json:{key} changed its placeholders"


def test_every_native_script_file_is_translated_not_copied():
    english = load("en")
    for code in ("bn", "gu", "kn", "ml", "pa", "ta", "te"):
        data = load(code)
        shared = [key for key, value in data.items() if value == english[key]]
        # A handful of keys ("meta_action", "Amount"…) can coincide, but the
        # file as a whole must be a real translation.
        assert len(shared) < len(data) // 4, f"{code}.json is mostly English"


def test_frontend_uses_one_setting_and_no_old_dropdown():
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert 'id="ui-lang"' not in html
    assert "ui-lang" not in app.replace("vk-ui-lang", "")
    assert "hisabsetu_lang" in app
    # The old interface-only storage key survives only in the migration.
    assert app.count("vk-ui-lang") <= 3

    assert "/static/i18n.js" in html
    assert html.index("/static/i18n.js") < html.index("/static/app.js")


def test_header_switch_finds_the_chosen_button_positionally():
    # Regression: once English is chosen, the chosen button also carries
    # data-voice-lang="en-IN", so excluding en-IN left no button to update and
    # the toggle got stuck showing English twice after a modal switch.
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'querySelectorAll("button")' in app
    assert ':not([data-voice-lang="en-IN"])' not in app


def test_no_string_key_renders_as_a_raw_key():
    english = load("en")
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    used = set(re.findall(r'\bt\(\s*"([a-z0-9_]+)"', app))
    used |= set(re.findall(r'data-i18n(?:-aria|-ph|-title)?="([a-z0-9_]+)"', html))
    assert used, "no keys found — the extractor is broken"
    missing = sorted(key for key in used if key not in english)
    assert not missing, f"frontend asks for keys English does not define: {missing}"


def test_switching_language_changes_the_visible_text():
    steps = {code: load(code)["step1"] for code in ("en", "hi", "ta", "bn", "te")}
    assert len(set(steps.values())) == len(steps)
    titles = {code: load(code)["app_title"] for code in ("hi", "ml", "pa")}
    assert len(set(titles.values())) == len(titles)


def test_server_texts_follow_the_active_language():
    tamil = tr("ta-IN", "confirmed_credit", name="Ramesh", amount="₹150", balance="₹0")
    english = tr("en-IN", "confirmed_credit", name="Ramesh", amount="₹150", balance="₹0")
    hindi = tr("hi-IN", "confirmed_credit", name="Ramesh", amount="₹150", balance="₹0")
    assert tamil != english
    assert "₹150" in tamil and "{amount}" not in tamil
    assert "udhaar" in hindi  # Hinglish unchanged for Hindi


def test_unknown_language_falls_back_to_english_never_hinglish():
    assert tr("xx-XX", "err_empty_text") == tr("en-IN", "err_empty_text")
    assert tr(None, "err_empty_text") == tr("hi-IN", "err_empty_text")


def test_preview_and_confirmation_return_the_requested_language(client, db):
    from conftest import make_customer

    # The canonical fold maps ரமேஷ் → Ramesh, the same path the voice
    # translator output takes.
    make_customer(db, "Ramesh")
    preview = client.post(
        "/api/command",
        json={"text": "Ramesh 150 udhaar", "language": "ta-IN", "source": "voice"},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["kind"] == "proposal", body
    assert body["message"] == tr(
        "ta-IN",
        "preview_credit_msg",
        name="Ramesh",
        amount=body["proposal"]["amount_text"],
    )

    pending_id = body["proposal"]["pending_id"]
    confirmed = client.post(f"/api/pending/{pending_id}/confirm?lang=ta-IN")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["message"].startswith("Ramesh")

    english = client.post(f"/api/pending/{pending_id}/confirm?lang=en-IN")
    assert english.status_code == 200
    assert "was already saved" in english.json()["message"].lower()


def test_daily_summary_accepts_a_language(client):
    response = client.get("/api/daily-summary?lang=bn-IN")
    assert response.status_code == 200
    assert "বাকি" in response.json()["reply_text"]


def test_manifest_name_follows_the_language(client):
    tamil = client.get("/manifest.webmanifest?lang=ta-IN")
    english = client.get("/manifest.webmanifest")
    assert tamil.status_code == 200 and english.status_code == 200
    assert tamil.json()["name"] != english.json()["name"]
    assert tamil.json()["lang"] == "ta"
