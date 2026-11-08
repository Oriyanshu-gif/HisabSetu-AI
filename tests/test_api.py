"""FastAPI endpoint tests. Gnani is mocked; no key or network is required."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

import gnani_client
from conftest import make_customer, make_wav, post_entry
from gnani_client import SttResult, TtsResult


def transaction_count(client) -> int:
    return client.get("/api/dashboard").json()["transaction_count"]


@pytest.fixture
def gnani_configured(monkeypatch):
    """Configure the *shared* configuration source.

    The endpoint guard (``main.require_configured``) and ``transcribe()`` /
    ``synthesize()`` both read ``gnani_client.settings`` — the same object the
    app uses in production.  Patching the endpoint only (the old style) hid the
    fact that the two gates could disagree.
    """
    fake = replace(gnani_client.settings, gnani_api_key="test-key-123")
    monkeypatch.setattr(gnani_client, "settings", fake)
    return fake


# ---------------------------------------------------------------------------
# Static UI and status
# ---------------------------------------------------------------------------


def test_root_serves_the_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "HisabSetu AI" in response.text
    assert "Boliye, main likh dunga" in response.text
    assert "app.js" in response.text
    # The old working title leaked into the noscript fallback and /api/health,
    # so a public demo showed one brand in the header and another in the API.
    assert "KhataVaani" not in response.text
    assert client.get("/api/health").json()["app"] == "HisabSetu AI"


def test_static_assets_are_served(client):
    css = client.get("/static/styles.css")
    js = client.get("/static/app.js")
    assert css.status_code == 200
    assert "--green-700" in css.text
    assert js.status_code == 200
    assert "confirmProposal" in js.text


def test_pwa_manifest_is_served_at_the_root(client):
    """The manifest must live at / so `scope` covers the app and Chrome offers install."""
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = response.json()
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any("maskable" in icon.get("purpose", "") for icon in manifest["icons"])
    # Every icon the manifest promises must actually be served.
    for icon in manifest["icons"]:
        assert client.get(icon["src"]).status_code == 200


def test_service_worker_is_served_with_root_scope(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert response.headers["service-worker-allowed"] == "/"
    # A money app must never serve a cached ledger from the worker.
    assert 'url.pathname.startsWith("/api/")' in response.text


def test_the_page_registers_the_service_worker(client):
    html = client.get("/").text
    assert 'rel="manifest"' in html
    assert 'serviceWorker.register("/sw.js")' in html
    assert "apple-touch-icon" in html


def test_history_labels_are_not_the_brand_name(client):
    """Section labels stay plain shopkeeper wording, never the app name."""
    # The strings now live in static/i18n/<code>.json, loaded on demand.
    hindi = json.loads(client.get("/static/i18n/hi.json").text)
    english = json.loads(client.get("/static/i18n/en.json").text)
    assert hindi["txn_history"] == "पुरानी एंट्री"
    assert hindi["recent_entries"] == "हाल की एंट्री"
    assert english["txn_history"] == "Transaction history"
    assert english["recent_entries"] == "Recent entries"
    # The brand name must not be used as the section label in any locale.
    for code in ("en", "hi", "hing", "mr", "bn", "gu", "kn", "ml", "pa", "ta", "te"):
        label = json.loads(client.get(f"/static/i18n/{code}.json").text)["txn_history"]
        assert "KhataVaani" not in label
        assert "खातावाणी" not in label


def test_no_user_facing_string_keeps_the_old_working_title(client):
    """The UI ships one brand. i18n used to overwrite the header and footer."""
    js = client.get("/static/app.js").text
    page = client.get("/").text
    sweep = client.get("/static/mic_sweep.html").text
    assert '"KhataVaani"' not in js
    assert "KhataVaani" not in page
    assert "KhataVaani" not in sweep
    # Brand strings are per-language files now; every locale keeps HisabSetu AI.
    for code in ("en", "hi", "hing", "mr", "bn", "gu", "kn", "ml", "pa", "ta", "te"):
        strings = json.loads(client.get(f"/static/i18n/{code}.json").text)
        assert strings["voice_khata"] == "HisabSetu AI"
        assert strings["footer_tag"] == "HisabSetu AI"
        assert "KhataVaani" not in " ".join(strings.values())


def test_health_reports_unconfigured_voice(client):
    payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    assert payload["gnani"]["configured"] is False
    assert payload["gnani"]["mode"] == "unconfigured"
    assert "ffmpeg_available" in payload["audio"]
    assert payload["ledger_convention"].startswith("credit increases")
    assert "api_key" not in json.dumps(payload).lower()


def test_health_never_leaks_the_configured_key(client, monkeypatch):
    import gnani_client

    secret = "sk-super-secret-do-not-leak"
    monkeypatch.setattr(gnani_client, "settings", replace(gnani_client.settings, gnani_api_key=secret))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["gnani"]["configured"] is True
    assert secret not in response.text


# ---------------------------------------------------------------------------
# Ledger reads
# ---------------------------------------------------------------------------


def test_dashboard_empty_ledger(client):
    payload = client.get("/api/dashboard").json()
    assert payload["total_outstanding_paise"] == 0
    assert payload["customer_count"] == 0
    assert payload["sample_data"] is False
    assert payload["today_credit_text"] == "₹0"


def test_customers_endpoint_and_search(client, db):
    make_customer(db, "Ramesh")
    make_customer(db, "Sunita")
    payload = client.get("/api/customers").json()
    assert payload["count"] == 2
    assert {row["name"] for row in payload["customers"]} == {"Ramesh", "Sunita"}

    filtered = client.get("/api/customers?search=ram").json()
    assert filtered["count"] == 1
    assert filtered["customers"][0]["name"] == "Ramesh"


def test_create_customer_explicitly_and_reject_duplicates(client):
    created = client.post("/api/customers", json={"name": "Kavita"})
    assert created.status_code == 201
    body = created.json()["customer"]
    assert body["name"] == "Kavita"
    assert body["balance_paise"] == 0
    assert body["is_sample"] is False

    duplicate = client.post("/api/customers", json={"name": "kavita"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "customer_exists"

    invalid = client.post("/api/customers", json={"name": "12345"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_customer_name"

    assert client.post("/api/customers", json={"name": "A"}).status_code == 422
    assert client.get("/api/dashboard").json()["transaction_count"] == 0


class TestCustomerCreation:
    def test_new_customer_can_receive_a_transaction(self, client):
        client.post("/api/customers", json={"name": "Nisha"})
        preview = client.post(
            "/api/command", json={"text": "Nisha ko dedh sau rupaye ka udhaar likh do"}
        ).json()
        assert preview["kind"] == "proposal"
        assert preview["proposal"]["customer"]["name"] == "Nisha"


def test_customer_detail_and_404(client, db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 150)
    payload = client.get(f"/api/customers/{ramesh.id}").json()
    assert payload["customer"]["balance_text"] == "₹150"
    assert payload["transactions"][0]["amount_text"] == "₹150"

    missing = client.get("/api/customers/9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "unknown_customer"


def test_transactions_limit_is_bounded(client):
    assert client.get("/api/transactions?limit=0").status_code == 422
    assert client.get("/api/transactions?limit=500").status_code == 422


# ---------------------------------------------------------------------------
# Command -> confirm flow through HTTP
# ---------------------------------------------------------------------------


def test_command_preview_then_confirm(client, db):
    ramesh = make_customer(db, "Ramesh")
    before = transaction_count(client)

    preview = client.post(
        "/api/command",
        json={"text": "Ramesh ko dedh sau rupaye ka udhaar likh do", "source": "voice"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["kind"] == "proposal"
    assert body["proposal"]["customer"]["id"] == ramesh.id
    assert body["proposal"]["amount_text"] == "₹150"
    assert body["proposal"]["balance_after_text"] == "₹150"
    assert transaction_count(client) == before

    confirm = client.post(f"/api/pending/{body['proposal']['pending_id']}/confirm", json={})
    assert confirm.status_code == 200
    result = confirm.json()
    assert result["already_confirmed"] is False
    assert result["transaction"]["amount_paise"] == 15000
    assert result["customer"]["balance_paise"] == 15000
    assert transaction_count(client) == before + 1

    again = client.post(f"/api/pending/{body['proposal']['pending_id']}/confirm", json={})
    assert again.status_code == 200
    assert again.json()["already_confirmed"] is True
    assert transaction_count(client) == before + 1


def test_assumed_dedh_warning_reaches_the_preview_card(client, db):
    # Exact transcript Prisma returned when the speaker said "dedh sau".
    ramesh = make_customer(db, "Ramesh")
    before = transaction_count(client)

    body = client.post(
        "/api/command",
        json={"text": "रमेश को दे दो सौ रुपए का उधार लिख दो", "source": "voice"},
    ).json()

    assert body["kind"] == "proposal"
    proposal = body["proposal"]
    assert proposal["customer"]["id"] == ramesh.id
    # The bug was a ₹100 transaction; it must now be ₹150.
    assert proposal["amount_text"] == "₹150"
    assert proposal["warning"] == "assumed_dedh"
    assert "Dhyan dein" in proposal["message"]
    assert "Sahi karein" in proposal["message"]
    # The top-level message mirrors the card, not a stale copy.
    assert body["message"] == proposal["message"]
    assert transaction_count(client) == before


def test_confirmed_assumed_dedh_posts_one_fifty(client, db):
    make_customer(db, "Ramesh")
    before = transaction_count(client)
    pending_id = client.post(
        "/api/command",
        json={"text": "रमेश को दे दो सौ रुपए का उधार लिख दो", "source": "voice"},
    ).json()["proposal"]["pending_id"]

    result = client.post(f"/api/pending/{pending_id}/confirm", json={}).json()
    assert result["transaction"]["amount_paise"] == 15000
    assert transaction_count(client) == before + 1


def test_plain_dedh_preview_has_no_warning(client, db):
    make_customer(db, "Ramesh")
    body = client.post(
        "/api/command",
        json={"text": "Ramesh ko dedh sau rupaye ka udhaar likh do", "source": "voice"},
    ).json()
    assert body["kind"] == "proposal"
    assert "warning" not in body["proposal"]
    assert "Dhyan dein" not in body["proposal"]["message"]


def test_command_requires_non_empty_text(client):
    assert client.post("/api/command", json={"text": ""}).status_code == 422
    assert client.post("/api/command", json={}).status_code == 422


def test_command_unknown_customer_returns_clarification(client, db):
    make_customer(db, "Ramesh")
    response = client.post(
        "/api/command", json={"text": "Ramessh ko 500 rupaye ka udhaar likh do"}
    ).json()
    assert response["kind"] == "clarification"
    assert response["clarification"]["customers"]
    assert transaction_count(client) == 0


def test_cancel_endpoint_does_not_change_ledger(client, db):
    make_customer(db, "Ramesh")
    preview = client.post(
        "/api/command", json={"text": "Ramesh ko 200 rupaye ka udhaar likh do"}
    ).json()
    pending_id = preview["proposal"]["pending_id"]

    cancel = client.post(f"/api/pending/{pending_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["kind"] == "cancelled"
    assert transaction_count(client) == 0

    status = client.get(f"/api/pending/{pending_id}").json()
    assert status["status"] == "cancelled"


def test_pending_not_found(client):
    assert client.get("/api/pending/nope").status_code == 404
    assert client.post("/api/pending/nope/confirm", json={}).status_code == 404


def test_overpayment_acknowledgement_via_api(client, db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 100)

    preview = client.post(
        "/api/command", json={"text": "Ramesh ne 500 rupaye wapas kar diye"}
    ).json()
    proposal = preview["proposal"]
    assert proposal["requires_overpayment_ack"] is True

    blocked = client.post(f"/api/pending/{proposal['pending_id']}/confirm", json={})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "overpayment_ack_required"
    assert transaction_count(client) == 1

    allowed = client.post(
        f"/api/pending/{proposal['pending_id']}/confirm",
        json={"acknowledge_overpayment": True},
    )
    assert allowed.status_code == 200
    assert allowed.json()["customer"]["balance_paise"] == -40000


def test_balance_query_returns_answer_without_pending(client, db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 250)
    response = client.post(
        "/api/command", json={"text": "Ramesh ka kitna udhaar baaki hai"}
    ).json()
    assert response["kind"] == "answer"
    assert response["answer"]["kind"] == "balance"
    assert response["answer"]["balance_text"] == "₹250"
    assert response["speech_text"]
    assert client.get("/api/pending/anything").status_code == 404


def test_manual_proposal_endpoint(client, db):
    ramesh = make_customer(db, "Ramesh")
    response = client.post(
        "/api/manual-proposal",
        json={"customer_id": ramesh.id, "type": "credit", "amount_rupees": "99.50"},
    )
    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["amount_text"] == "₹99.50"
    assert transaction_count(client) == 0


def test_manual_proposal_validates_amount(client, db):
    ramesh = make_customer(db, "Ramesh")
    response = client.post(
        "/api/manual-proposal",
        json={"customer_id": ramesh.id, "type": "credit", "amount_rupees": "0"},
    )
    assert response.status_code == 422


def test_daily_summary_and_top_debtors_endpoints(client, db):
    ramesh = make_customer(db, "Ramesh")
    sunita = make_customer(db, "Sunita")
    post_entry(db, ramesh, "credit", 500)
    post_entry(db, sunita, "credit", 900)

    summary = client.get("/api/daily-summary").json()
    assert summary["credit_paise"] >= 140000
    assert summary["credit_text"].startswith("₹")
    assert summary["top_debtors"][0]["name"] == "Sunita"
    assert summary["reminders"]

    top = client.get("/api/top-debtors?limit=1").json()
    assert len(top["customers"]) == 1
    assert top["customers"][0]["name"] == "Sunita"

    invalid = client.get("/api/daily-summary?date=26-10-2026")
    assert invalid.status_code == 422


# ---------------------------------------------------------------------------
# Voice endpoints (mocked provider)
# ---------------------------------------------------------------------------


def test_stt_is_503_without_a_key(client):
    response = client.post(
        "/api/stt", files={"file": ("voice.wav", make_wav(1), "audio/wav")}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "gnani_not_configured"


def test_stt_rejects_empty_audio(client, gnani_configured):
    response = client.post("/api/stt", files={"file": ("voice.wav", b"", "audio/wav")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_audio"


def test_stt_uses_mocked_gnani_and_returns_transcript(client, gnani_configured, monkeypatch):
    import main

    captured = {}

    def fake_transcribe(wav_bytes, language=None, audio_format=None):
        captured["size"] = len(wav_bytes)
        captured["language"] = language
        captured["audio_format"] = audio_format
        return SttResult(
            transcript="Ramesh ko dedh sau rupaye ka udhaar likh do",
            request_id="req_test",
            model="gnani-prisma-v2.5",
        )

    monkeypatch.setattr(main, "transcribe", fake_transcribe)

    response = client.post(
        "/api/stt",
        files={"file": ("voice.webm", make_wav(1), "audio/wav")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["transcript"].startswith("Ramesh")
    assert body["provider"] == "gnani-prisma"
    assert body["request_id"] == "req_test"
    assert body["audio"]["converted"] is False
    assert captured["size"] > 1000


def test_tts_is_503_without_a_key(client):
    response = client.post("/api/tts", json={"text": "नमस्ते"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "gnani_not_configured"


def test_tts_returns_binary_audio_when_mocked(client, gnani_configured, monkeypatch):
    import main

    def fake_synthesize(text, language=None, voice=None):
        return TtsResult(audio=b"RIFF" + b"\x00" * 120, content_type="audio/wav")

    monkeypatch.setattr(main, "synthesize", fake_synthesize)

    response = client.post("/api/tts", json={"text": "नमस्ते"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["x-voice-provider"] == "gnani-timbre"
    assert response.content.startswith(b"RIFF")


def test_tts_rejects_overlong_text(client, gnani_configured):
    response = client.post("/api/tts", json={"text": "क" * 500})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tts_text_too_long"


# ---------------------------------------------------------------------------
# TTS status contract: one configuration gate, no false success
# ---------------------------------------------------------------------------


def test_configuration_source_is_shared_by_app_and_client():
    """main.py and gnani_client must read the same settings object.

    This is the regression guard for "the app and the Gnani client disagree
    about whether the key is configured": if either module ever binds its own
    copy, the endpoint guard and the actual call can drift apart.
    """
    import config
    import gnani_client as client_module
    import main

    assert main.settings is config.settings
    assert client_module.settings is config.settings
    assert main.require_configured is client_module.require_configured


def test_missing_key_is_503_at_the_shared_gate(client):
    """Missing key -> 503 / gnani_not_configured, from either layer."""
    import gnani_client as client_module

    with pytest.raises(client_module.GnaniNotConfigured) as error:
        client_module.require_configured("text-to-speech")
    assert error.value.status_code == 503
    assert error.value.code == "gnani_not_configured"

    response = client.post("/api/tts", json={"text": "नमस्ते"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "gnani_not_configured"
    assert response.json()["error"]["hint"]

    stt = client.post("/api/stt", files={"file": ("voice.wav", make_wav(1), "audio/wav")})
    assert stt.status_code == 503
    assert stt.json()["error"]["code"] == "gnani_not_configured"


def test_tts_configured_success_returns_real_audio_bytes(client, gnani_configured, monkeypatch):
    """Configured + provider returns WAV -> 200 with actual audio bytes."""
    import httpx

    import gnani_client as client_module

    audio = b"RIFF" + b"\x00" * 256
    monkeypatch.setattr(
        client_module,
        "_post",
        lambda url, **kwargs: httpx.Response(
            200, content=audio, headers={"content-type": "audio/wav"}
        ),
    )

    response = client.post("/api/tts", json={"text": "नमस्ते"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content == audio
    assert response.headers["x-voice-provider"] == "gnani-timbre"


def test_tts_provider_error_is_never_reported_as_success(client, gnani_configured, monkeypatch):
    """Configured + provider answers with a JSON error -> 502, not 200/503."""
    import httpx

    import gnani_client as client_module

    monkeypatch.setattr(
        client_module,
        "_post",
        lambda url, **kwargs: httpx.Response(
            200, json={"detail": "voice not found"}, headers={"content-type": "application/json"}
        ),
    )
    response = client.post("/api/tts", json={"text": "नमस्ते"})
    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "gnani_tts_error"
    assert "voice not found" in body["message"]


def test_tts_empty_body_is_not_a_success(client, gnani_configured, monkeypatch):
    """A 200 from the provider with no bytes must not become a 200 here."""
    import httpx

    import gnani_client as client_module

    monkeypatch.setattr(
        client_module,
        "_post",
        lambda url, **kwargs: httpx.Response(200, content=b"", headers={"content-type": "audio/wav"}),
    )
    response = client.post("/api/tts", json={"text": "नमस्ते"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "gnani_empty_audio"


def test_tts_network_failure_reports_provider_error_not_missing_key(client, gnani_configured, monkeypatch):
    """Key present but unreachable -> 502 gnani_network_error, never 503."""
    import httpx

    import gnani_client as client_module

    def boom(url, **kwargs):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(client_module, "_post", boom)
    response = client.post("/api/tts", json={"text": "नमस्ते"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "gnani_network_error"


def test_health_explains_the_configuration_source_without_leaking_it(client, gnani_configured):
    payload = client.get("/api/health").json()
    assert payload["gnani"]["configured"] is True
    assert payload["gnani"]["config_source"] in {"process_env", "env_file", "process_env_empty", "none"}
    assert "test-key-123" not in json.dumps(payload)


def test_health_reports_process_env_blank_when_env_file_was_ignored(client):
    """A blank GNANI_API_KEY in the environment wins over .env — say so."""
    from config import gnani_key_source

    # tests/conftest.py deliberately blanks the key before the app is imported,
    # so this process reports the blanking explicitly instead of a bare "none".
    assert gnani_key_source() == "process_env_empty"
    payload = client.get("/api/health").json()
    assert payload["gnani"]["configured"] is False
    assert payload["gnani"]["config_source"] == "process_env_empty"


# ---------------------------------------------------------------------------
# Cross-script customer matching (Prisma returns Devanagari for Hindi speech)
# ---------------------------------------------------------------------------


def test_devanagari_transcript_links_a_latin_customer(client, db):
    """सुनीता in the transcript must reach the customer typed as "Sunita"."""
    sunita = make_customer(db, "Sunita")

    preview = client.post(
        "/api/command",
        json={"text": "सुनीता को दो सौ रुपये का उधार लिख दो", "source": "voice"},
    ).json()
    assert preview["kind"] == "proposal"
    assert preview["proposal"]["customer"]["id"] == sunita.id
    assert preview["proposal"]["amount_text"] == "₹200"
    assert transaction_count(client) == 0

    result = client.post(f"/api/pending/{preview['proposal']['pending_id']}/confirm", json={}).json()
    assert result["customer"]["balance_paise"] == 20000
    assert transaction_count(client) == 1


def test_latin_transcript_links_a_devanagari_spoken_name(client, db):
    """A typed Latin command still reaches a customer recorded in Devanagari."""
    ramesh = make_customer(db, "रमेश")

    preview = client.post(
        "/api/command", json={"text": "Ramesh ko dedh sau rupaye ka udhaar likh do"}
    ).json()
    assert preview["kind"] == "proposal"
    assert preview["proposal"]["customer"]["id"] == ramesh.id
    assert preview["proposal"]["amount_text"] == "₹150"


def test_honorific_variants_resolve_to_one_customer(client, db):
    """ji / bhai / shri are how the speaker talks, not a second person."""
    ramesh = make_customer(db, "Ramesh")

    for text in (
        "रमेश भाई को तीन सौ का उधार लिख दो",
        "रमेश जी को तीन सौ का उधार लिख दो",
        "श्री रमेश को तीन सौ का उधार लिख दो",
    ):
        preview = client.post("/api/command", json={"text": text}).json()
        assert preview["kind"] == "proposal", (text, preview)
        assert preview["proposal"]["customer"]["id"] == ramesh.id
        assert preview["proposal"]["amount_text"] == "₹300"


def test_duplicate_customer_in_another_script_is_rejected(client, db):
    """One person must never get two ledger rows (which would split balances)."""
    assert client.post("/api/customers", json={"name": "Sunita"}).status_code == 201
    duplicate = client.post("/api/customers", json={"name": "सुनीता"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "customer_exists"
    assert client.get("/api/customers").json()["count"] == 1


def test_duplicate_customer_with_honorific_is_rejected(client):
    assert client.post("/api/customers", json={"name": "Ramesh"}).status_code == 201
    assert client.post("/api/customers", json={"name": "रमेश भाई"}).status_code == 409


def test_uncertain_name_returns_candidates_and_requires_explicit_choice(client, db):
    """Similar names must never be resolved by a guess."""
    make_customer(db, "Ramesh")
    make_customer(db, "Ramesh Kumar")

    response = client.post(
        "/api/command", json={"text": "Ram ko do sau rupaye ka udhaar likh do"}
    ).json()
    assert response["kind"] == "clarification"
    assert response["clarification"]["needs"] == ["customer"]
    names = {row["name"] for row in response["clarification"]["customers"]}
    assert names == {"Ramesh", "Ramesh Kumar"}
    assert response["proposal"] is None
    assert transaction_count(client) == 0

    # Explicit selection completes the same instruction safely.
    chosen = client.post(
        "/api/command",
        json={"text": "Ram ko do sau rupaye ka udhaar likh do", "customer_id": 1},
    ).json()
    assert chosen["kind"] == "proposal"
    assert chosen["proposal"]["customer"]["name"] == "Ramesh"
    assert transaction_count(client) == 0


def test_two_rows_sharing_a_key_are_reported_as_ambiguous(client, db):
    """Even a corrupted ledger must ask, not pick the first row."""
    from services import resolve_customer

    make_customer(db, "Sunita")
    make_customer(db, "Suneeta")  # folds to the same canonical key

    customer, suggestions, status = resolve_customer(db, "सुनीता")
    assert customer is None
    assert status == "ambiguous"
    assert {row["name"] for row in suggestions} == {"Sunita", "Suneeta"}


# ---------------------------------------------------------------------------
# Compound utterances
# ---------------------------------------------------------------------------


def test_compound_credit_and_payment_asks_for_one_command_at_a_time(client, db):
    make_customer(db, "Ramesh")
    make_customer(db, "Sunita")

    response = client.post(
        "/api/command",
        json={
            "text": "Ramesh ko dedh sau rupaye ka udhaar likh do aur Sunita ne do sau rupaye wapas kar diye"
        },
    ).json()

    assert response["kind"] == "clarification"
    assert response["clarification"]["needs"] == ["compound"]
    commands = response["clarification"]["commands"]
    assert len(commands) == 2
    assert [row["intent"] for row in commands] == ["add_credit", "record_payment"]
    assert [row["amount_text"] for row in commands] == ["₹150", "₹200"]
    assert response["proposal"] is None
    # Nothing was written and nothing was half-executed.
    assert transaction_count(client) == 0
    assert client.get("/api/dashboard").json()["total_outstanding_paise"] == 0


def test_compound_never_silently_drops_the_transaction_half(client, db):
    """"Aaj ka hisaab + credit" used to answer the summary and drop the credit."""
    make_customer(db, "Ramesh")

    response = client.post(
        "/api/command",
        json={"text": "Aaj ka poora hisaab batao aur Ramesh ko 200 ka udhaar likh do"},
    ).json()

    assert response["kind"] == "clarification"
    assert response["clarification"]["needs"] == ["compound"]
    intents = [row["intent"] for row in response["clarification"]["commands"]]
    assert "daily_summary" in intents
    assert "add_credit" in intents
    assert response["answer"] is None
    assert transaction_count(client) == 0


def test_single_command_with_a_trailing_comma_is_not_compound(client, db):
    make_customer(db, "Ramesh")
    response = client.post(
        "/api/command", json={"text": "Ramesh ko 150 rupaye ka udhaar likh do, theek hai?"}
    ).json()
    assert response["kind"] == "proposal"
    assert response["proposal"]["amount_text"] == "₹150"


def test_noisy_filler_after_aur_is_not_treated_as_compound(client, db):
    """The noisy fixture appends filler after और — it is one payment, not two."""
    make_customer(db, "Sunita")
    response = client.post(
        "/api/command",
        json={
            "text": "सुनीता ने दो सौ रूपए वापस कर दिए और गलतियां होने पर बिना जज के करेक्ट करूँगी "
            "अच्छा कल से ही शुरू करूँगी"
        },
    ).json()
    assert response["kind"] == "proposal"
    assert response["proposal"]["amount_text"] == "₹200"
    assert transaction_count(client) == 0


# ---------------------------------------------------------------------------
# Transcript / detail correction before confirmation
# ---------------------------------------------------------------------------


def test_correction_rebuilds_the_preview_and_still_writes_nothing(client, db):
    ramesh = make_customer(db, "Ramesh")

    first = client.post(
        "/api/command", json={"text": "Ramesh ko 150 rupaye ka udhaar likh do"}
    ).json()["proposal"]
    assert first["amount_text"] == "₹150"
    assert first["balance_after_text"] == "₹150"

    corrected = client.post(
        "/api/manual-proposal",
        json={
            "customer_id": ramesh.id,
            "type": "credit",
            "amount_rupees": "250",
            "transcript": "Ramesh ko 250 rupaye ka udhaar likh do",
        },
    ).json()["proposal"]

    # The preview is recalculated from the corrected details.
    assert corrected["amount_text"] == "₹250"
    assert corrected["balance_before_text"] == "₹0"
    assert corrected["balance_after_text"] == "₹250"
    assert corrected["transcript"] == "Ramesh ko 250 rupaye ka udhaar likh do"
    assert corrected["pending_id"] != first["pending_id"]
    # Still nothing on the ledger.
    assert transaction_count(client) == 0

    confirmed = client.post(f"/api/pending/{corrected['pending_id']}/confirm", json={}).json()
    assert confirmed["transaction"]["amount_paise"] == 25000
    assert confirmed["transaction"]["transcript"] == "Ramesh ko 250 rupaye ka udhaar likh do"
    assert transaction_count(client) == 1

    # The superseded preview can never be confirmed into a second entry later:
    # cancel it explicitly and it stays cancelled.
    cancel = client.post(f"/api/pending/{first['pending_id']}/cancel")
    assert cancel.status_code == 200
    assert client.post(f"/api/pending/{first['pending_id']}/confirm", json={}).status_code == 409
    assert transaction_count(client) == 1


def test_transcript_correction_reparses_and_rebuilds_the_preview(client, db):
    """Fixing the transcript itself must re-parse, not re-use the old amount.

    Prisma heard "सवा सौ" (₹125) but the shopkeeper meant "सवा दो सौ" (₹225).
    Re-sending the corrected transcript has to produce a *new* preview with the
    new amount, and the ledger must stay untouched until Confirm.
    """
    mohan = make_customer(db, "Mohan")

    heard = client.post(
        "/api/command", json={"text": "मोहन को सवा सौ का उधार लिख दो"}
    ).json()["proposal"]
    assert heard["amount_text"] == "₹125"
    assert transaction_count(client) == 0

    corrected = client.post(
        "/api/command", json={"text": "मोहन को सवा दो सौ का उधार लिख दो"}
    ).json()["proposal"]

    assert corrected["amount_text"] == "₹225"
    assert corrected["balance_after_text"] == "₹225"
    assert corrected["customer"]["id"] == mohan.id
    assert corrected["pending_id"] != heard["pending_id"]
    assert transaction_count(client) == 0  # still only previews

    confirmed = client.post(f"/api/pending/{corrected['pending_id']}/confirm", json={}).json()
    assert confirmed["transaction"]["amount_paise"] == 22500
    assert transaction_count(client) == 1

    # The superseded preview (₹125) cannot be confirmed into a second entry.
    assert client.post(f"/api/pending/{heard['pending_id']}/cancel").status_code == 200
    assert client.post(f"/api/pending/{heard['pending_id']}/confirm", json={}).status_code == 409
    assert transaction_count(client) == 1


def test_reparsing_the_same_transcript_never_double_posts(client, db):
    """Re-sending the identical text creates another preview, not another entry."""
    make_customer(db, "Ramesh")
    text = {"text": "Ramesh ko 150 rupaye ka udhaar likh do"}

    first = client.post("/api/command", json=text).json()["proposal"]
    second = client.post("/api/command", json=text).json()["proposal"]
    assert first["pending_id"] != second["pending_id"]
    assert transaction_count(client) == 0

    client.post(f"/api/pending/{second['pending_id']}/confirm", json={})
    assert transaction_count(client) == 1
    assert client.post(f"/api/pending/{first['pending_id']}/confirm", json={}).status_code == 409
    assert transaction_count(client) == 1


def test_payment_correction_recomputes_the_overpayment_gate(client, db):
    ramesh = make_customer(db, "Ramesh")
    from conftest import post_entry

    post_entry(db, ramesh, "credit", 100)

    small = client.post(
        "/api/manual-proposal",
        json={"customer_id": ramesh.id, "type": "payment", "amount_rupees": "50"},
    ).json()["proposal"]
    assert small["requires_overpayment_ack"] is False
    assert small["balance_after_text"] == "₹50"

    big = client.post(
        "/api/manual-proposal",
        json={"customer_id": ramesh.id, "type": "payment", "amount_rupees": "500"},
    ).json()["proposal"]
    assert big["requires_overpayment_ack"] is True
    assert big["balance_after_text"] == "-₹400"

    blocked = client.post(f"/api/pending/{big['pending_id']}/confirm", json={})
    assert blocked.status_code == 409
    assert transaction_count(client) == 1  # only the seeded entry
