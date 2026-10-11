"""Tool registry + built-in, sandboxed tools."""
import ast
import ipaddress
import operator
import os
import socket
import urllib.request
from typing import Callable
from urllib.parse import urlparse

from .memory import Memory

MAX_OUTPUT = 5000


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, name: str, description: str, properties: dict, required: list[str], fn: Callable):
        self._tools[name] = {
            "spec": {
                "name": name,
                "description": description,
                "input_schema": {"type": "object", "properties": properties, "required": required},
            },
            "fn": fn,
        }

    def specs(self, allowed: list[str] | None = None) -> list[dict]:
        return [t["spec"] for n, t in self._tools.items() if allowed is None or n in allowed]

    def call(self, name: str, args: dict, allowed: list[str] | None = None) -> str:
        if name not in self._tools or (allowed is not None and name not in allowed):
            return f"ERROR: tool '{name}' is not available."
        try:
            return str(self._tools[name]["fn"](**args))[:MAX_OUTPUT]
        except Exception as e:  # tool errors go back to the model so it can recover
            return f"ERROR: {type(e).__name__}: {e}"


# ---------- safe calculator ----------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv, ast.USub: operator.neg}


def calculator(expression: str):
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            if isinstance(n.op, ast.Pow) and abs(ev(n.right)) > 100:
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        raise ValueError("unsupported expression")
    return ev(ast.parse(expression, mode="eval").body)


def build_registry(workspace: str, memory: Memory) -> ToolRegistry:
    root = os.path.realpath(workspace)
    os.makedirs(root, exist_ok=True)

    def safe_path(rel: str) -> str:
        p = os.path.realpath(os.path.join(root, rel))
        if p != root and not p.startswith(root + os.sep):
            raise PermissionError("path escapes workspace")
        return p

    def read_file(path: str):
        with open(safe_path(path)) as f:
            return f.read()

    def write_file(path: str, content: str):
        p = safe_path(path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
        return f"wrote {len(content)} chars to {path}"

    def list_files(path: str = "."):
        return "\n".join(sorted(os.listdir(safe_path(path)))) or "(empty)"

    def http_get(url: str):
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError("only http(s) URLs allowed")
        for info in socket.getaddrinfo(u.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise PermissionError("private/loopback addresses blocked")
        req = urllib.request.Request(url, headers={"User-Agent": "agentic-agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read(MAX_OUTPUT * 2).decode("utf-8", "replace")

    r = ToolRegistry()
    s = {"type": "string"}
    r.register("calculator", "Evaluate an arithmetic expression.", {"expression": s}, ["expression"], calculator)
    r.register("read_file", "Read a text file from the workspace.", {"path": s}, ["path"], read_file)
    r.register("write_file", "Write a text file in the workspace.", {"path": s, "content": s}, ["path", "content"], write_file)
    r.register("list_files", "List files in a workspace directory.", {"path": s}, [], list_files)
    r.register("http_get", "Fetch a public web page (text).", {"url": s}, ["url"], http_get)
    r.register("remember", "Save a durable note for future runs.", {"text": s}, ["text"],
               lambda text: (memory.add(text), "saved")[1])
    r.register("recall", "Search saved notes by keywords.", {"query": s}, ["query"],
               lambda query: "\n".join(memory.recall(query)) or "no matching notes")
    r.register("finish", "Call when the goal is complete, with the final answer.", {"answer": s}, ["answer"],
               lambda answer: answer)
    return r


def default_registry(workspace: str = "workspace", memory: Memory | None = None) -> ToolRegistry:
    return build_registry(workspace, memory or Memory())
