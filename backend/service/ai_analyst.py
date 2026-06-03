# ── HuggingFace Free Tier — Developer Notes ──────────────────────────
# Model roster is tried in priority order. Automatic fallback occurs on:
#   503 (model cold start — sleeps after inactivity, ~20-60s to wake)
#   429 (rate limit — free tier is throttled on rapid calls)
#   404 (model removed or renamed on HuggingFace Hub)
#
# Coding-capable models in roster (in priority order):
#   1. Mistral-7B-Instruct-v0.3  — best free instruction model overall
#   2. Mistral-7B-Instruct-v0.2  — stable fallback, same family
#   3. Qwen2.5-Coder-7B-Instruct — best free model for code + structured text
#   4. Phi-3.5-mini-instruct      — fast, low latency, reliable on free tier
#   5. Zephyr-7B-beta             — well-tested fallback, widely available
#   6. Falcon-7B-instruct         — last resort, older but stable
#
# To use a local Ollama instance instead, replace BASE_URL with:
#   http://localhost:11434/api/generate
# and adjust the payload format to Ollama's schema.
#
# SECURITY: HF_API_TOKEN is loaded from .env only. Never log it.
#   Mask it in all error messages: token[:8] + "..."
# ─────────────────────────────────────────────────────────────────────

import json
import logging
import time
import requests

import config

logger = logging.getLogger("cricviz.ai_analyst")

BASE_URL = "https://api-inference.huggingface.co/models/{model_id}"


def _build_prompt(context: dict, context_type: str) -> str:
    """
    Cricket analyst prompt template.
    Instruction-tuned models expect [INST] / [/INST] tags (Mistral format).
    Wrap prompt accordingly so it works across all roster models:
    """
    if context_type == "over":
        instruction = """Analyze the following sequence of deliveries (an over) and write a concise insight paragraph (maximum 100 words).
Focus on momentum shifts, dot-ball pressure, boundary responses, and key wickets.
Describe the narrative of the over. Do not repeat raw ball-by-ball numbers — interpret their impact on the match situation."""
    else:
        instruction = f"""Analyze the following {context_type} data and write a concise insight paragraph (maximum 100 words).
Focus on xR, xW, false shot percentage, and shot intent distribution.
Be specific. Do not repeat raw numbers — interpret their meaning in context."""

    return f"""[INST] You are a cricket data analyst. {instruction}
Do not use generic phrases like 'performed well' or 'showed promise'.

Data:
{json.dumps(context, indent=2)}

Write only the insight paragraph. No preamble, no labels. [/INST]"""


def _call_model(model_id: str, prompt: str) -> dict:
    """
    Returns {"status": "ok"|"skip", "text": "...", "reason": "..."}
    "skip" means caller should try next model.
    """
    headers = {
        "Authorization": f"Bearer {config.HF_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": config.HF_MAX_NEW_TOKENS,
            "temperature": config.HF_TEMPERATURE,
            "return_full_text": False,
            "do_sample": True,
            "repetition_penalty": 1.1
        }
    }

    url = BASE_URL.format(model_id=model_id)

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=config.HF_TIMEOUT_SECONDS)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                    text = data[0]["generated_text"].strip()
                    return {"status": "ok", "text": text, "reason": ""}
                else:
                    return {"status": "skip", "text": "", "reason": "bad_response_format"}
            except json.JSONDecodeError:
                return {"status": "skip", "text": "", "reason": "bad_response_format"}

        elif response.status_code == 503:
            logger.warning(f"Model {model_id} cold start (503). Retrying once in 20s...")
            time.sleep(20)
            retry_resp = requests.post(url, headers=headers, json=payload, timeout=config.HF_TIMEOUT_SECONDS)
            if retry_resp.status_code == 200:
                try:
                    data = retry_resp.json()
                    if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                        return {"status": "ok", "text": data[0]["generated_text"].strip(), "reason": ""}
                except Exception:
                    pass
            return {"status": "skip", "text": "", "reason": "loading"}
            
        elif response.status_code == 429:
            return {"status": "skip", "text": "", "reason": "rate_limited"}
        elif response.status_code == 404:
            return {"status": "skip", "text": "", "reason": "model_not_found"}
        elif response.status_code == 401:
            # STOP iteration, raise immediately
            raise ValueError("bad_token")
        elif response.status_code >= 500:
            return {"status": "skip", "text": "", "reason": "server_error"}
        else:
            return {"status": "skip", "text": "", "reason": f"http_{response.status_code}"}

    except requests.Timeout:
        return {"status": "skip", "text": "", "reason": "timeout"}
    except ValueError as e:
        if str(e) == "bad_token":
            raise
        return {"status": "skip", "text": "", "reason": "unknown_error"}
    except Exception as e:
        logger.error(f"Error calling model {model_id}: {e}")
        return {"status": "skip", "text": "", "reason": "unknown_error"}


def generate_analyst_insight(context: dict, context_type: str) -> dict:
    """
    Returns:
      {
        "insight"    : "<text>",
        "model_used" : "<model_id> or none",
        "attempt"    : N,
        "status"     : "ok" | "fallback"
      }
    Never raises. Always returns the dict.
    """
    prompt = _build_prompt(context, context_type)

    roster = [config.HF_PRIMARY_MODEL] + [m for m in config.HF_MODEL_ROSTER if m != config.HF_PRIMARY_MODEL]

    for attempt, model_id in enumerate(roster, start=1):
        try:
            result = _call_model(model_id, prompt)
        except ValueError as e:
            if str(e) == "bad_token":
                logger.error("HuggingFace API token is invalid (401). Check .env file.")
                break
            continue
            
        if result["status"] == "ok":
            return {
                "insight": result["text"],
                "model_used": model_id,
                "attempt": attempt,
                "status": "ok"
            }
        else:
            logger.warning(f"Model {model_id} failed on attempt {attempt}. Reason: {result['reason']}")

    return {
        "insight": "AI Analysis is currently unavailable. Free tier models may be rate-limited or experiencing a cold start. Please try again later.",
        "model_used": "none",
        "attempt": len(roster),
        "status": "fallback"
    }


def prewarm_models() -> None:
    """
    Fire-and-forget prewarming ping to the primary HuggingFace model.
    Wakes it from 503 cold sleep so it's ready for the user.
    """
    logger.info(f"Pre-warming primary model: {config.HF_PRIMARY_MODEL}")
    prompt = "[INST] ping [/INST]"
    
    # We do a fast non-blocking request without retries just to trigger VRAM load
    headers = {
        "Authorization": f"Bearer {config.HF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 5, "return_full_text": False}
    }
    url = BASE_URL.format(model_id=config.HF_PRIMARY_MODEL)
    
    try:
        # We expect a 503 or 200. Timeout short because we just want to hit it.
        requests.post(url, headers=headers, json=payload, timeout=3)
    except Exception:
        pass # Ignore timeouts or errors, the goal is just to ping the endpoint
