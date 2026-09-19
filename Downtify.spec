# Build on macOS with make desktop-build.
import shutil
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH)
version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
binaries = []
for tool in ('ffmpeg', 'ffprobe', 'deno'):
    source = shutil.which(tool)
    if source is None:
        raise SystemExit(f'Missing {tool}; install with brew install ffmpeg deno')
    binaries.append((source, 'bin'))

if not (root / 'frontend/dist/index.html').is_file():
    raise SystemExit('Build the frontend first: npm run build --prefix frontend')

a = Analysis(
    ['desktop.py'],
    pathex=[str(root)],
    binaries=binaries,
    datas=[(str(root / 'frontend/dist'), 'frontend/dist')]
    + collect_data_files('ytmusicapi') + collect_data_files('yt_dlp_ejs'),
    hiddenimports=collect_submodules('yt_dlp_ejs'),
    excludes=['pytest', 'codeflash', 'tkinter', 'PyQt5', 'PyQt6', 'PySide6'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='Downtify', console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='Downtify')
app = BUNDLE(
    coll, name='Downtify.app',
    icon=str(root / 'build/Downtify.icns'),
    bundle_identifier='io.downtify.desktop', version=version,
    info_plist={
        'NSHighResolutionCapable': True,
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        'NSMusicFolderUsageDescription': 'Downtify saves your music library here.',
    },
)
