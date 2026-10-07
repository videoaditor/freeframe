"""Execute the production shell chain without requiring a Docker daemon in pytest."""
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

import pytest
import yaml


API = yaml.safe_load((Path(__file__).parents[3] / "docker-compose.prod.yml").read_text())["services"]["api"]


@pytest.fixture
def launch(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "apps/api").mkdir(parents=True)
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    migration = tmp_path / "migration.json"
    ready = tmp_path / "ready.json"
    programs = {
        "alembic": f"""import json, os, pathlib, sys
pathlib.Path({str(migration)!r}).write_text(json.dumps({{"cwd": os.getcwd(), "args": sys.argv[1:]}}))
sys.exit(int(os.environ.get("MIGRATION_EXIT", "0")))
""",
        "gunicorn": f"""import json, os, pathlib, signal, sys
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
pathlib.Path({str(ready)!r}).write_text(json.dumps({{"cwd": os.getcwd(), "pid": os.getpid()}}))
signal.pause()
""",
    }
    for name, source in programs.items():
        executable = executable_dir / name
        executable.write_text(f"#!{sys.executable}\n" + source)
        executable.chmod(0o755)
    command = shlex.split(API["command"].replace("$$", "$"))
    command[2] = command[2].replace("/workspace", str(workspace))
    processes = []

    def start(migration_exit=0):
        env = {**os.environ, "PATH": str(executable_dir) + os.pathsep + os.environ["PATH"],
               "MIGRATION_EXIT": str(migration_exit)}
        process = subprocess.Popen(command, env=env, start_new_session=True)
        processes.append(process)
        return process, workspace, migration, ready

    yield start
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def test_api_receives_term_after_successful_migration(launch):
    process, workspace, migration, ready = launch()
    deadline = time.monotonic() + 5
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ready.exists(), "API did not start after migration"
    assert json.loads(migration.read_text()) == {"cwd": str(workspace / "apps/api"), "args": ["upgrade", "head"]}
    server = json.loads(ready.read_text())
    assert server["cwd"] == str(workspace)
    assert server["pid"] == process.pid, "Shell must hand its PID and Docker TERM signal to Gunicorn"
    process.terminate()
    assert process.wait(timeout=5) == 0


def test_failed_migration_does_not_start_api(launch):
    process, _, migration, ready = launch(migration_exit=17)
    assert process.wait(timeout=5) == 17
    assert json.loads(migration.read_text())["args"] == ["upgrade", "head"]
    assert not ready.exists()


def test_docker_allows_gunicorn_to_finish_its_graceful_shutdown():
    command = shlex.split(shlex.split(API["command"])[2])
    gunicorn_grace = int(command[command.index("--graceful-timeout") + 1])
    docker_grace = API.get("stop_grace_period", "10s")
    assert docker_grace.endswith("s")
    assert float(docker_grace[:-1]) > gunicorn_grace, "Docker must not SIGKILL workers before Gunicorn's grace expires"
