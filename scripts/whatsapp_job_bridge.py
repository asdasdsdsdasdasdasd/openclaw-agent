#!/usr/bin/env python3
import json
import os
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "job-agent" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = ROOT / "job-agent" / ".whatsapp-bridge-state.json"
TASK_LOG = LOG_DIR / "whatsapp-task.log"
APP_LOG = LOG_DIR / "applications.log"
LAST_PREVIEW = LOG_DIR / "last_email_preview.txt"
JOB_LEADS = ROOT / "job-agent" / "job-leads.json"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"pid": None, "command": "", "logPath": str(TASK_LOG)}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"pid": None, "command": "", "logPath": str(TASK_LOG)}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def tail_lines(path: Path, n: int = 8) -> str:
    if not path.exists():
        return "(no file)"
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return "(empty)"
    return "\n".join(lines[-n:])


def launch_task(task: str) -> str:
    state = load_state()
    pid = state.get("pid")
    if is_pid_running(pid):
        return f"已有任务在运行 (pid={pid})，先等它完成。"

    if task == "job dry":
        cmd = [str(ROOT / "scripts" / "run-openclaw-autonomous-job-agent.sh"), "dry"]
    elif task == "job run":
        cmd = [str(ROOT / "scripts" / "run-openclaw-autonomous-job-agent.sh"), "send"]
    elif task == "job auto":
        cmd = [str(ROOT / "scripts" / "run-job-agent-daily.sh")]
    else:
        return f"不支持的任务: {task}"

    with TASK_LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n=== START task={task} ===\n")
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )
    save_state({"pid": proc.pid, "command": " ".join(cmd), "logPath": str(TASK_LOG)})
    return f"任务已启动: {task} (pid={proc.pid})"


def job_status() -> str:
    state = load_state()
    pid = state.get("pid")
    running = is_pid_running(pid)
    status = "running" if running else "idle"
    last_logs = tail_lines(TASK_LOG, n=10)
    return (
        f"状态: {status}\n"
        f"pid: {pid}\n"
        f"cmd: {state.get('command', '')}\n"
        f"--- 最近任务日志 ---\n{last_logs}"
    )


def job_last() -> str:
    app_tail = tail_lines(APP_LOG, n=5)
    leads = tail_lines(JOB_LEADS, n=20)
    preview = tail_lines(LAST_PREVIEW, n=12)
    return (
        f"--- applications.log ---\n{app_tail}\n\n"
        f"--- job-leads.json(尾部) ---\n{leads}\n\n"
        f"--- last_email_preview.txt(尾部) ---\n{preview}"
    )


def parse_command(body: str) -> str:
    return " ".join(body.strip().lower().split())


def run_command(raw: str) -> str:
    cmd = parse_command(raw)
    if cmd in {"help", "h", "?"}:
        return (
            "可用命令:\n"
            "- job dry   (OpenClaw agent 只写信草稿，不发邮件)\n"
            "- job run   (OpenClaw agent 跑一次并发送测试邮件)\n"
            "- job auto  (先dry再full)\n"
            "- job status\n"
            "- job last"
        )
    if cmd in {"job dry", "job run", "job auto"}:
        return launch_task(cmd)
    if cmd == "job status":
        return job_status()
    if cmd == "job last":
        return job_last()
    return "未知命令。发 help 查看可用命令。"


def twiml(message: str) -> bytes:
    safe = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'
    return xml.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/whatsapp":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8", errors="ignore")
        form = parse_qs(payload)
        body = (form.get("Body", [""])[0] or "").strip()
        from_number = (form.get("From", [""])[0] or "").strip()

        allowed = (os.getenv("WHATSAPP_ALLOWED_FROM", "") or "").strip()
        if allowed and from_number.lower() != allowed.lower():
            resp = "未授权号码。"
        else:
            secret = (os.getenv("WHATSAPP_BRIDGE_SECRET", "") or "").strip()
            if secret:
                if not body.startswith(secret + " "):
                    resp = "口令错误。"
                else:
                    resp = run_command(body[len(secret) + 1 :])
            else:
                resp = run_command(body)

        out = twiml(resp)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"whatsapp_job_bridge: ok\n")

    def log_message(self, fmt: str, *args) -> None:
        # Keep stdout clean; write simple server logs into task log if needed.
        return


def main() -> None:
    host = os.getenv("WHATSAPP_BRIDGE_HOST", "127.0.0.1")
    port = int(os.getenv("WHATSAPP_BRIDGE_PORT", "8787"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"whatsapp bridge listening on http://{host}:{port}/whatsapp")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
