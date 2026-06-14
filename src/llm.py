"""Shared LLM calling utilities for kiro-cli and ollama backends."""

import json
import os
import re
import subprocess
import time

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9]*[a-zA-Z]')


def strip_ansi(text):
    return ANSI_RE.sub('', text)


def call_kiro(prompt, model="claude-sonnet-4.6", agent="blank-agent",
              trust_tools="", timeout=600, cwd=None):
    """Call kiro-cli and return stripped output."""
    cmd = ["kiro-cli", "chat", "--no-interactive", "--model", model]
    if agent:
        cmd += ["--agent", agent]
    cmd += [f"--trust-tools={trust_tools}"]

    result = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True,
        timeout=timeout, cwd=cwd or PROJECT_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kiro-cli failed (exit {result.returncode}): {result.stderr[:300]}")
    return strip_ansi(result.stdout).strip()


def extract_json(text):
    """Extract a JSON object from LLM output (handles markdown fences, ANSI, raw JSON)."""
    text = strip_ansi(text)
    # Try markdown fence
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try raw JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None
