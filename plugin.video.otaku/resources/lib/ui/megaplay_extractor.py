"""MegaPlay video source extractor for Anikoto embed URLs."""
import json
import re
import urllib.parse

from resources.lib.ui import client, control


def extract_megaplay_sources(embed_url, referer=None):
    """
    Extract stream data from megaplay.buzz embed URLs (Anikoto API).

    Returns dict with sources, tracks, intro, outro — or None on failure.
    """
    referer = referer or 'https://anikototv.to/'
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0'

    try:
        headers = {
            'User-Agent': user_agent,
            'Referer': referer,
        }
        response = client.get(embed_url, headers=headers, timeout=15)
        if not response or not response.text:
            return None

        match = re.search(
            r'id="megaplay-player"[^>]*data-id="(\d+)"',
            response.text,
            re.I,
        )
        if not match:
            match = re.search(r'data-id="(\d+)"[^>]*data-realid=', response.text, re.I)
        if not match:
            control.log(f"MegaPlay: No player id in embed page: {embed_url}", level='info')
            return None

        player_id = match.group(1)
        api_url = 'https://megaplay.buzz/stream/getSources?id={0}'.format(player_id)
        api_headers = headers.copy()
        api_headers['X-Requested-With'] = 'XMLHttpRequest'
        api_headers['Referer'] = embed_url

        api_response = client.get(api_url, headers=api_headers, timeout=15)
        if not api_response or not api_response.text:
            return None

        data = api_response.json()
        sources = data.get('sources')
        if isinstance(sources, dict):
            file_url = sources.get('file')
            if file_url:
                data['sources'] = [{'file': file_url}]
        elif not sources:
            return None

        return data
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        control.log(f"MegaPlay extractor error: {e}", level='info')
        return None
    except Exception as e:
        control.log(f"MegaPlay extractor error: {e}", level='error')
        return None
