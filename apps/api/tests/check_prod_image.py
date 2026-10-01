"""Run inside the production image: Gunicorn must start as its non-root user."""
import os
import subprocess
import time
import urllib.error
import urllib.request


def main():
    assert os.getuid() != 0, "Production image must run as a non-root user"
    server = subprocess.Popen(
        ["gunicorn", "wsgiref.simple_server:demo_app", "--bind", "127.0.0.1:8000", "--workers", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ready = False
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and server.poll() is None:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000", timeout=1) as response:
                    ready = response.status == 200
                    if ready:
                        break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.1)
    finally:
        server.terminate()
        try:
            logs, _ = server.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            logs, _ = server.communicate()
    assert ready, f"Gunicorn did not serve HTTP successfully:\n{logs}"
    assert "[ERROR]" not in logs and "[CRITICAL]" not in logs, logs
    print("Production image: non-root Gunicorn startup and HTTP response passed without errors")


if __name__ == "__main__":
    main()
