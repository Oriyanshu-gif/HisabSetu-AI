"""End-to-end live check: TTS of the target phrase -> /api/stt -> command -> confirm.

Exercises the same endpoints the browser mic flow uses, with real Gnani STT.
Never prints GNANI_API_KEY.
"""
from __future__ import annotations

import json
import sys

import httpx

from gnani_client import synthesize

BASE = "http://127.0.0.1:8000"
PHRASE = "Ramesh ko dedh sau rupaye ka udhaar likh do"


def main() -> int:
    # 1. Synthesize the exact phrase the user would speak.
    tts = synthesize(PHRASE)
    print(f"[1] TTS OK: {len(tts.audio)} bytes {tts.content_type}")
    print(f"    source phrase: {PHRASE}")

    # 2. POST it to /api/stt exactly like the browser upload.
    with httpx.Client(base_url=BASE, timeout=60.0) as client:
        r = client.post(
            "/api/stt",
            files={"file": ("mic.wav", tts.audio, "audio/wav")},
            data={"filename": "mic.wav"},
        )
        print(f"[2] /api/stt -> {r.status_code}")
        if r.status_code != 200:
            print("    " + json.dumps(r.json(), ensure_ascii=False, indent=2))
            return 1
        transcript = r.json().get("transcript")
        print(f"    PRISMA TRANSCRIPT: {transcript!r}")

        # 3. Parse it into a preview card.
        r2 = client.post("/api/command", json={"text": transcript})
        print(f"[3] /api/command -> {r2.status_code}")
        body = r2.json()
        print("    " + json.dumps(body, ensure_ascii=False, indent=2))
        if r2.status_code not in (200, 201):
            return 1
        proposal = body.get("proposal") or body
        pending_id = (proposal.get("pending_id")
                      or body.get("pending_id")
                      or body.get("id"))
        if not pending_id:
            print("    !! no pending_id returned, cannot confirm")
            return 1

        # 4. Confirm -> posts to the ledger once.
        r3 = client.post(f"/api/pending/{pending_id}/confirm")
        print(f"[4] confirm -> {r3.status_code}")
        print("    " + json.dumps(r3.json(), ensure_ascii=False, indent=2))
        if r3.status_code not in (200, 201):
            return 1

    print("\nE2E LIVE FLOW OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
