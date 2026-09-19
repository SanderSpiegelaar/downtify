"""Focused checks for desktop configuration and the real backend lifecycle."""

import json
import multiprocessing
import socket
import urllib.request
from unittest.mock import Mock

import pytest

pytest.importorskip('webview')
import desktop  # noqa: E402


def test_windows_support_directory_uses_local_app_data(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop.sys, 'platform', 'win32')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    assert desktop.support_directory() == tmp_path / 'Downtify'


def test_instance_lock_prevents_overlap_and_releases(tmp_path):
    path = tmp_path / 'desktop.lock'
    with path.open('a+b') as first, path.open('a+b') as second:
        desktop.lock_instance(first)
        with pytest.raises(OSError, match='.+'):
            desktop.lock_instance(second)
    with path.open('a+b') as reopened:
        desktop.lock_instance(reopened)


@pytest.fixture
def support(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    for key in (
        'DATABASE_DIR',
        'DOWNLOAD_DIR',
        'WEB_GUI_LOCATION',
        'DOWNTIFY_COOKIES_FROM_BROWSER',
    ):
        monkeypatch.delenv(key, raising=False)
    # Restore PATH and desktop variables after configuration mutates them.
    monkeypatch.setenv('PATH', '/usr/bin:/bin')
    return tmp_path


def test_folder_picker_persists_both_choices_for_next_launch(support):
    locations = desktop.configure_environment(support)
    config = support / 'desktop.json'
    chosen = support / 'My Music'
    chosen.mkdir()
    window = Mock()
    window.create_file_dialog.return_value = (str(chosen),)
    window.create_confirmation_dialog.return_value = True

    desktop.choose_location(window, config, locations, 'DOWNLOAD_DIR')

    saved = json.loads(config.read_text())
    assert saved['DOWNLOAD_DIR'] == str(chosen)
    assert saved['DATABASE_DIR'] == str(support / 'data')
    # The running backend keeps its current paths until restart.
    assert desktop.os.environ['DOWNLOAD_DIR'] != str(chosen)
    desktop.os.environ.pop('DOWNLOAD_DIR')
    assert desktop.configure_environment(support)['DOWNLOAD_DIR'] == str(
        chosen
    )


@pytest.mark.parametrize(
    ('selection', 'confirmed'), [(None, True), (('/tmp',), False)]
)
def test_cancel_folder_change_does_not_write(support, selection, confirmed):
    config = support / 'desktop.json'
    locations = desktop.configure_environment(support)
    window = Mock()
    window.create_file_dialog.return_value = selection
    window.create_confirmation_dialog.return_value = confirmed
    desktop.choose_location(window, config, locations, 'DATABASE_DIR')
    assert not config.exists()


def test_environment_overrides_saved_locations(support, monkeypatch):
    (support / 'desktop.json').write_text(
        json.dumps({
            'DOWNLOAD_DIR': str(support / 'saved music'),
            'DATABASE_DIR': str(support / 'saved data'),
        })
    )
    monkeypatch.setenv('DATABASE_DIR', str(support / 'override'))
    locations = desktop.configure_environment(support)
    assert locations['DATABASE_DIR'] == str(support / 'override')
    assert locations['DOWNLOAD_DIR'] == str(support / 'saved music')


def test_desktop_always_uses_chrome_cookies(support, monkeypatch):
    monkeypatch.setenv('DOWNTIFY_COOKIES_FROM_BROWSER', 'firefox')
    desktop.configure_environment(support)
    assert desktop.os.environ['DOWNTIFY_COOKIES_FROM_BROWSER'] == 'chrome'


def test_backend_serves_ui_and_api_and_stops(support, monkeypatch):
    desktop.configure_environment(support)
    ui = support / 'frontend'
    ui.mkdir()
    (ui / 'index.html').write_text('<html>Desktop smoke test</html>')
    monkeypatch.setenv('WEB_GUI_LOCATION', str(ui))
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        url = f'http://127.0.0.1:{listener.getsockname()[1]}'
        process = multiprocessing.get_context('spawn').Process(
            target=desktop.serve,
            args=(listener, support / 'desktop.log'),
        )
        process.start()
        try:
            desktop.wait_until_ready(process, url)
            client = urllib.request.build_opener(
                urllib.request.ProxyHandler({})
            )
            with client.open(url, timeout=2) as response:
                assert b'Desktop smoke test' in response.read()
            with client.open(f'{url}/api/version', timeout=2) as response:
                assert response.status == 200
        finally:
            desktop.stop_backend(process)
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', int(url.rsplit(':', 1)[1]))) != 0


def test_failed_backend_does_not_wait_for_timeout():
    process = Mock()
    process.is_alive.return_value = False
    with pytest.raises(RuntimeError, match='did not start'):
        desktop.wait_until_ready(process, 'http://127.0.0.1:1')
