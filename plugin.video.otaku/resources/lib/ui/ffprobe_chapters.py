"""
Optional ffprobe-based chapter metadata for resolved play URLs.

Kodi (and inputstream.ffmpegdirect) use FFmpeg libraries for demux/playback but
do not expose a Python API to list container chapters on Omega. Running ffprobe
against the same URL Kodi will play is the practical way to collect chapter
names/times before or during resolve.

See: https://github.com/xbmc/inputstream.ffmpegdirect (playback path, not metadata API)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.parse

from resources.lib.ui import control

_ffprobe_cached: str | None = False  # type: ignore[assignment]


def _xbmc_bin_dir() -> str:
    try:
        exe = getattr(sys, 'executable', '') or ''
        if exe and os.path.isfile(exe):
            return os.path.dirname(exe)
    except Exception:
        pass
    try:
        return control.xbmcvfs.translatePath('special://xbmc')
    except Exception:
        return ''


def find_ffprobe() -> str | None:
    """Return path to ffprobe if found, else None."""
    global _ffprobe_cached
    if _ffprobe_cached not in (False, None):
        return _ffprobe_cached or None

    candidates = []

    custom = (control.getStr('ffprobe.path') or '').strip().strip('"')
    if custom:
        candidates.append(custom)

    which = shutil.which('ffprobe')
    if which:
        candidates.append(which)
    if sys.platform == 'win32':
        w = shutil.which('ffprobe.exe')
        if w:
            candidates.append(w)

    base = _xbmc_bin_dir()
    if base:
        if sys.platform == 'win32':
            candidates.extend([
                os.path.join(base, 'ffprobe.exe'),
                os.path.join(base, 'ffmpeg', 'ffprobe.exe'),
                os.path.join(base, 'tools', 'ffmpeg', 'bin', 'ffprobe.exe'),
            ])
        else:
            candidates.extend([
                os.path.join(base, 'ffprobe'),
                os.path.join(base, 'ffmpeg', 'ffprobe'),
                os.path.join(base, 'tools', 'ffmpeg', 'bin', 'ffprobe'),
            ])

    for path in candidates:
        if path and os.path.isfile(path):
            _ffprobe_cached = path
            control.log(f'ffprobe: using {path}', 'debug')
            return path

    _ffprobe_cached = None
    return None


def _split_url_headers(play_url: str) -> tuple[str, dict[str, str]]:
    if '|' not in play_url:
        return play_url, {}
    url, hdrs = play_url.split('|', 1)
    headers = {}
    for pair in hdrs.split('&'):
        if '=' not in pair:
            continue
        k, v = pair.split('=', 1)
        headers[k] = urllib.parse.unquote_plus(v)
    return url, headers


def _headers_ffprobe_arg(headers: dict) -> str | None:
    if not headers:
        return None
    lines = []
    for key, value in headers.items():
        if value is None:
            continue
        k = str(key).strip()
        if not k:
            continue
        lines.append(f'{k}: {str(value).strip()}')
    if not lines:
        return None
    return '\r\n'.join(lines) + '\r\n'


def _should_probe_url(clean_url: str, content_type: str, is_local: bool) -> bool:
    ct = (content_type or '').lower()
    u = clean_url.lower()
    path_only = u.split('?')[0]

    if path_only.endswith(('.mkv', '.mp4', '.m4v', '.webm')):
        return True

    if 'm3u8' in u or '.mpd' in u or 'manifest' in u:
        return False
    if 'mpegurl' in ct or 'mp2t' in ct or 'dash' in ct or 'm3u8' in ct:
        return False
    if 'video/x-matroska' in ct or 'matroska' in ct:
        return True
    if 'video/mp4' in ct or 'video/quicktime' in ct:
        return True
    if 'application/octet-stream' in ct and '.mkv' in u:
        return True
    if ct.startswith('video/') and 'mpegurl' not in ct and 'mp2t' not in ct:
        return True
    if clean_url.startswith('file://'):
        return True
    if is_local and (u.startswith('special://') or u.startswith('smb://') or u.startswith('nfs://')):
        return True
    if sys.platform == 'win32' and len(clean_url) > 2 and clean_url[1] == ':' and '\\' in clean_url:
        return True
    if clean_url.startswith('/'):
        try:
            if os.path.isfile(control.xbmcvfs.translatePath(clean_url)):
                return True
        except Exception:
            pass
    return False


def probe_stream_chapters(ffprobe_path: str, play_url: str, timeout: int = 18) -> list[dict]:
    """
    Return chapter dicts: index, title, start (seconds float), end (seconds float).
    play_url may include Kodi-style '|Cookie=...&User-Agent=...' suffix.
    """
    clean_url, hdrs = _split_url_headers(play_url)
    if not clean_url:
        return []

    args = [
        ffprobe_path,
        '-v', 'error',
        '-hide_banner',
        '-print_format', 'json',
        '-show_chapters',
        '-probesize', '33554432',
        '-analyzeduration', '10000000',
    ]
    h = _headers_ffprobe_arg(hdrs)
    if h:
        args.extend(['-headers', h])
    args.extend(['-i', clean_url])

    creationflags = 0
    startupinfo = None
    if sys.platform == 'win32':
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
    except subprocess.TimeoutExpired:
        control.log('ffprobe: chapter probe timed out', 'warning')
        return []
    except OSError as e:
        control.log(f'ffprobe: failed to run ({e})', 'warning')
        return []

    if proc.returncode != 0:
        err = (proc.stderr or '').strip()[:500]
        if err:
            control.log(f'ffprobe: exit {proc.returncode} — {err}', 'debug')
        return []

    try:
        data = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        return []

    out = []
    for i, ch in enumerate(data.get('chapters') or []):
        tags = ch.get('tags') or {}
        title = tags.get('title') or tags.get('TITLE') or f'Chapter {i + 1}'
        try:
            start = float(ch.get('start_time', 0))
        except (TypeError, ValueError):
            start = 0.0
        try:
            end = float(ch.get('end_time', start))
        except (TypeError, ValueError):
            end = start
        out.append({
            'index': i,
            'title': str(title).strip(),
            'start': start,
            'end': end,
        })
    return out


def attach_to_linkinfo(linkinfo: dict | None) -> None:
    """
    Mutates linkinfo to add 'chapters' (list, possibly empty).
    Uses Content-Type from prefetch headers when present.
    """
    if not linkinfo or not isinstance(linkinfo, dict):
        return

    linkinfo['chapters'] = []

    if not control.getBool('ffprobe.chapters.enable'):
        return

    exe = find_ffprobe()
    if not exe:
        control.log('ffprobe: binary not found (install FFmpeg or set ffprobe path in settings)', 'debug')
        return

    play_url = linkinfo.get('url') or linkinfo.get('link')
    if not play_url:
        return

    headers = linkinfo.get('headers') or {}
    content_type = ''
    if isinstance(headers, dict):
        content_type = headers.get('Content-Type') or headers.get('content-type') or ''

    is_local = bool(linkinfo.get('local'))
    if not _should_probe_url(_split_url_headers(str(play_url))[0], content_type, is_local):
        return

    chapters = probe_stream_chapters(exe, str(play_url))
    if chapters:
        linkinfo['chapters'] = chapters
        control.log(f'ffprobe: found {len(chapters)} chapter(s)', 'info')
