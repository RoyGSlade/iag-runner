from __future__ import annotations

import json
import os
from typing import Any

import requests

from gm_os.protocols import ProtocolId
from llm.schemas import Intent, NarrationRequest, SessionSetup, TurnEnvelope


class LLMClientError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL") or "http://localhost:11434").rstrip(
            "/"
        )
        self.model = model or os.getenv("OLLAMA_MODEL") or "gpt-oss:20b"
        if timeout is None:
            timeout = int(os.getenv("OLLAMA_TIMEOUT", "30"))
        self.timeout = timeout

    def extract_intent(self, player_text: str, context: dict | None = None) -> Intent:
        context_payload = context or {}
        attempts = 0
        last_error: str | None = None
        while attempts < 3:
            attempts += 1
            try:
                content = self._chat(
                    messages=_intent_messages(player_text, context_payload, attempts, last_error),
                    temperature=0,
                    format="json",
                )
                intent = _parse_intent(content)
                return intent
            except Exception as exc:
                last_error = str(exc)
        return _fallback_intent()

    def extract_intent_with_debug(
        self,
        player_text: str,
        context: dict | None = None,
    ) -> tuple[Intent, dict]:
        context_payload = context or {}
        attempts = 0
        last_error: str | None = None
        last_output: str | None = None
        errors: list[str] = []
        while attempts < 3:
            attempts += 1
            try:
                content = self._chat(
                    messages=_intent_messages(player_text, context_payload, attempts, last_error),
                    temperature=0,
                    format="json",
                )
                last_output = content
                intent = _parse_intent(content)
                return (
                    intent,
                    {
                        "raw_llm_output": content,
                        "parsed_intent": intent.model_dump(),
                        "validation_errors": errors,
                    },
                )
            except Exception as exc:
                last_error = str(exc)
                errors.append(last_error)
        return (
            _fallback_intent(),
            {
                "raw_llm_output": last_output,
                "parsed_intent": None,
                "validation_errors": errors,
            },
        )

    def generate_narration(self, narration_request: NarrationRequest) -> str:
        try:
            content = self._chat(
                messages=_narration_messages(narration_request),
                temperature=0.7,
            )
            return content.strip()
        except Exception:
            return "The scene pauses for clarification before continuing."

    def generate_turn_envelope(
        self,
        player_text: str,
        context: dict | None = None,
    ) -> TurnEnvelope:
        context_payload = context or {}
        attempts = 0
        last_error: str | None = None
        while attempts < 3:
            attempts += 1
            try:
                content = self._chat(
                    messages=_turn_envelope_messages(
                        player_text, context_payload, attempts, last_error
                    ),
                    temperature=0,
                    format="json",
                )
                envelope = _parse_turn_envelope(content)
                if (
                    envelope.council is not None
                    and not context_payload.get("dev_mode_enabled", False)
                    and envelope.confidence != "low"
                ):
                    raise LLMClientError(
                        "Council notes only allowed in dev mode or low confidence."
                    )
                return envelope
            except Exception as exc:
                last_error = str(exc)
        raise LLMClientError("Failed to build TurnEnvelope JSON.")

    def complete_session0(self, session0_input: dict[str, Any]) -> SessionSetup:
        attempts = 0
        last_error: str | None = None
        while attempts < 3:
            attempts += 1
            try:
                content = self._chat(
                    messages=_session0_messages(session0_input, attempts, last_error),
                    temperature=0.4,
                    format="json",
                )
                setup = _parse_session_setup(content)
                return setup
            except Exception as exc:
                last_error = str(exc)
        raise LLMClientError("Failed to build SessionSetup JSON.")

    def _chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        format: str | None = None,
    ) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format:
            payload["format"] = format
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMClientError("Invalid response from Ollama.")
        return content


def _intent_messages(
    player_text: str,
    context: dict,
    attempt: int,
    last_error: str | None,
) -> list[dict[str, str]]:
    system = (
        "You extract player intent as strict JSON only. "
        "Return a JSON object matching this schema: "
        "{"
        '"action_type": "explore|scene_request|interact|move|attack|use_power|buy_item|ask_gm|ask_clarifying_question|invalid|other", '
        '"targets": [{"id": 0, "name": "string", "type": "string"}], '
        '"skill_used": "string|null", '
        '"power_used": "string|null", '
        '"item_used": "string|null", '
        '"movement": {"mode": "walk|run|dash|teleport|none", "distance": 0, "destination": "string"}, '
        '"dialogue": "string|null", '
        '"reason": "string|null", '
        '"metadata": {"any": "json"}, '
        '"confidence": 0.0, '
        '"assumptions": ["string"]'
        "}. "
        "Choose the best-guess intent when plausible and include assumptions + confidence. "
        "Only use action_type ask_clarifying_question when absolutely necessary. "
        "If the request is illegal, return action_type invalid and set reason. "
        "Do not include commentary or markdown."
    )
    if attempt > 1 and last_error:
        system += f" Previous output invalid: {last_error}. Return JSON only."

    user = {
        "player_text": player_text,
        "context": {
            "era": context.get("era"),
            "available_actions": context.get("available_actions", []),
            "available_powers": context.get("available_powers", []),
            "notes": context.get("notes"),
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]


def _narration_messages(narration_request: NarrationRequest) -> list[dict[str, str]]:
    system = (
        "You narrate outcomes. Use the provided state summary and outcome only. "
        "Keep it concise and grounded. Do not alter mechanics. "
        "If current_scene.established is true, do not re-describe the scene. "
        "Describe only changes, new details, or newly relevant information. "
        "Never repeat the full scene summary and avoid the phrase 'What do you do next?'. "
        "If nothing changed, say so briefly."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": narration_request.model_dump_json()},
    ]


def _session0_messages(
    session0_input: dict[str, Any],
    attempt: int,
    last_error: str | None,
) -> list[dict[str, str]]:
    system = (
        "You produce a SessionSetup JSON object only. "
        "Return JSON matching this schema: "
        "{"
        '"era": "string", '
        '"setting": {"type": "string", "tone": ["string"], "inspirations": ["string"]}, '
        '"player_prefs": {"violence_level": "string", "horror": "string", "avoid": ["string"]}, '
        '"starting_situation": {"hook": "string", "first_scene": "string", '
        '"immediate_problem": "string", "npcs": ["string"]}'
        "}. "
        "No prose, no markdown, no extra keys."
    )
    if attempt > 1 and last_error:
        system += f" Previous output invalid: {last_error}. Return JSON only."

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(session0_input)},
    ]


def _turn_envelope_messages(
    player_text: str,
    context: dict[str, Any],
    attempt: int,
    last_error: str | None,
) -> list[dict[str, str]]:
    protocol_list = [proto.value for proto in ProtocolId]
    system = (
        "You must return JSON only for a TurnEnvelope. "
        "Choose mode: gm|ooc|dev. "
        "Pick protocol_id from the provided protocol list only. "
        "If unclear, include up to 3 ooc_questions. "
        "Include dev_report only if dev_mode_enabled is true. "
        "Only include council notes when dev_mode_enabled is true OR confidence is low. "
        "Schema: {"
        '"mode": "gm|ooc|dev", '
        '"protocol_id": "string", '
        '"confidence": "high|medium|low", '
        '"classification": {"primary_category": "string", "secondary_category": "string|null"}, '
        '"ooc_questions": ["string"], '
        '"gm_plan": [{"type": "move|attack|interact|investigate|social|use_power|craft|improvise|downtime", '
        '"actor_id": 0, "targets": ["string"], "skill_used": "string|null", '
        '"power_used": "string|null", "time_cost": "none|action|reaction|minutes|hours|days", '
        '"risk_level": "low|med|high", "notes": "string", "complexity": 1} ] | null, '
        '"content_requests": [{"any": "json"}] | null, '
        '"memory_suggestions": {"any": "json"} | null, '
        '"dev_report": {"any": "json"} | null, '
        '"council": {"planner_notes": "string|null", "validator_notes": "string|null", '
        '"lorekeeper_notes": "string|null", "director_notes": "string|null", '
        '"speaker_outline": "string|null"} | null'
        "}. "
        "No extra keys, no markdown."
    )
    if attempt > 1 and last_error:
        system += f" Previous output invalid: {last_error}. Return JSON only."

    user = {
        "player_text": player_text,
        "context": {
            "era": context.get("era"),
            "scene_summary": context.get("scene_summary"),
            "dev_mode_enabled": context.get("dev_mode_enabled", False),
            "protocols": protocol_list,
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]


def _parse_intent(content: str) -> Intent:
    payload = _extract_json(content)
    return Intent.model_validate(payload)


def _parse_turn_envelope(content: str) -> TurnEnvelope:
    payload = _extract_json(content)
    return TurnEnvelope.model_validate(payload)


def _parse_session_setup(content: str) -> SessionSetup:
    payload = _extract_json(content)
    return SessionSetup.model_validate(payload)


def _extract_json(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(content[start : end + 1])
        if isinstance(data, dict):
            return data
    raise LLMClientError("Failed to parse JSON intent.")


def _fallback_intent() -> Intent:
    return Intent(
        action_type="ask_clarifying_question",
        dialogue="Could you clarify your intended action?",
        targets=[],
        movement=None,
    )
