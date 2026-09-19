"""Native macOS and Windows launcher for the existing web app."""

from __future__ import annotations

import errno
import html
import json
import multiprocessing
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from functools import partial
from http import HTTPStatus
from pathlib import Path

import webview
from webview.menu import Menu, MenuAction

ROOT = Path(__file__).resolve().parent


def support_directory() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ['LOCALAPPDATA']) / 'Downtify'
    return Path.home() / 'Library/Application Support/Downtify'


def lock_instance(lock) -> None:
    if sys.platform == 'win32':
        import msvcrt  # noqa: PLC0415

        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl  # noqa: PLC0415

        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def configure_environment(support: Path) -> dict[str, str]:
    os.environ['DOWNTIFY_COOKIES_FROM_BROWSER'] = 'chrome'
    config = support / 'desktop.json'
    locations = {
        'DOWNLOAD_DIR': str(Path.home() / 'Music/Downtify'),
        'DATABASE_DIR': str(support / 'data'),
    }
    if config.exists():
        locations.update(json.loads(config.read_text()))
    for key in ('DOWNLOAD_DIR', 'DATABASE_DIR'):
        path = Path(os.environ.get(key, locations[key])).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        locations[key] = os.environ[key] = str(path)
    os.environ['WEB_GUI_LOCATION'] = str(ROOT / 'frontend/dist')
    # Native launchers do not inherit the shell PATH. Prefer bundled tools.
    paths = [str(ROOT / 'bin'), os.environ.get('PATH', '')]
    if sys.platform == 'darwin':
        paths[1:1] = ['/opt/homebrew/bin', '/usr/local/bin']
    os.environ['PATH'] = os.pathsep.join(paths)
    return locations


def choose_location(window, config: Path, locations: dict, key: str) -> None:
    selected = window.create_file_dialog(
        webview.FileDialog.FOLDER,
        directory=locations[key],
    )
    if not selected:
        return
    path = Path(selected[0]).resolve()
    if not window.create_confirmation_dialog(
        'Change library location?',
        f'Use {path} after restarting Downtify?\n\n'
        'Existing files are not moved. Select a folder containing your '
        'existing library or move your files there after quitting.',
    ):
        return
    updated = {**locations, key: str(path)}
    temporary = config.with_suffix('.tmp')
    temporary.write_text(json.dumps(updated, indent=2) + '\n')
    temporary.replace(config)
    locations.update(updated)


def serve(listener: socket.socket, log_path: Path) -> None:
    # Windowed PyInstaller apps have no stdout/stderr.
    with log_path.open('a', buffering=1, encoding='utf-8') as log:
        sys.stdout = sys.stderr = log
        # Import after streams and desktop paths are configured.
        from loguru import logger  # noqa: PLC0415
        from uvicorn import Config, Server  # noqa: PLC0415

        import main  # noqa: PLC0415

        main._setup_logging('info')
        main._fix_mime_types()
        try:
            server = Server(
                Config(
                    main.build_app(),
                    host='127.0.0.1',
                    loop='asyncio',
                    http='h11',
                    ws='websockets',
                    log_config=None,
                    timeout_graceful_shutdown=3,
                )
            )
            server.run(sockets=[listener])
        except Exception:
            logger.exception('Desktop backend failed')
            raise


def wait_until_ready(process, url: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while process.is_alive() and time.monotonic() < deadline:
        try:
            with client.open(f'{url}/api/health', timeout=0.5) as response:
                if response.status == HTTPStatus.OK:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.1)
    raise RuntimeError('The local server did not start. See desktop.log.')


def stop_backend(process) -> None:
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join()
    process.close()


def run_window(support: Path) -> None:
    process = None
    try:
        locations = configure_environment(support)
        if not (ROOT / 'frontend/dist/index.html').is_file():
            raise RuntimeError(
                'Build the frontend: npm run build --prefix frontend'
            )
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            url = f'http://127.0.0.1:{listener.getsockname()[1]}'
            process = multiprocessing.get_context('spawn').Process(
                target=serve,
                args=(listener, support / 'desktop.log'),
            )
            process.start()
            wait_until_ready(process, url)
            webview.settings['ALLOW_DOWNLOADS'] = True
            window = webview.create_window(
                'Downtify',
                url,
                width=1280,
                height=850,
                min_size=(800, 600),
                confirm_close=True,
            )
            choose = partial(
                choose_location,
                window,
                support / 'desktop.json',
                locations,
            )
            menu = [
                Menu(
                    'Library locations',
                    [
                        MenuAction(
                            'Choose music folder…',
                            partial(choose, 'DOWNLOAD_DIR'),
                        ),
                        MenuAction(
                            'Choose data folder…',
                            partial(choose, 'DATABASE_DIR'),
                        ),
                    ],
                )
            ]
            webview.start(
                gui='edgechromium' if sys.platform == 'win32' else None,
                private_mode=False,
                storage_path=str(support / 'webview'),
                menu=menu,
            )
    except Exception as exc:
        webview.create_window(
            'Downtify — startup failed',
            html=f'<h2>Downtify could not start</h2>'
            f'<p>{html.escape(str(exc))}</p>'
            f'<p>Logs: {html.escape(str(support / "desktop.log"))}</p>',
            width=640,
            height=300,
        )
        webview.start()
    finally:
        if process is not None and process.pid is not None:
            stop_backend(process)


def main() -> None:
    support = support_directory()
    support.mkdir(parents=True, exist_ok=True)
    with (support / 'desktop.lock').open('a+b') as lock:
        try:
            lock_instance(lock)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                return  # An instance already owns the desktop configuration.
            raise
        run_window(support)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
