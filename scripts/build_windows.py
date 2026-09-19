"""Build the Windows portable app using the desktop dependency extra."""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if sys.platform != 'win32':
        raise SystemExit('Build the Windows application on Windows.')
    root = Path(__file__).resolve().parent.parent
    for tool in ('npm', 'ffmpeg', 'ffprobe', 'deno'):
        if shutil.which(tool) is None:
            raise SystemExit(f'Install {tool} and add it to PATH first.')
    npm = shutil.which('npm')
    subprocess.run([npm, 'ci', '--prefix', 'frontend'], cwd=root, check=True)
    subprocess.run(
        [npm, 'run', 'build', '--prefix', 'frontend'],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--noconfirm', 'Downtify.spec'],
        cwd=root,
        check=True,
    )
    archive = shutil.make_archive(
        str(root / 'dist/Downtify-windows'),
        'zip',
        root_dir=root / 'dist',
        base_dir='Downtify',
    )
    print(f'Built {archive}. Extract it and run Downtify/Downtify.exe.')


if __name__ == '__main__':
    main()
