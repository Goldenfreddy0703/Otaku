"""MegaPlay video source extractor for Anikoto embed URLs."""
import base64
import json
import re

from resources.lib.ui import client, control, pyaes


def decrypt_megaplay_source(enc_data):
    key = b"i?LMTAx0Q6,:}50U" + b'\x00' * 16
    iv = b"W0;27ToaUpl_P%'c"
    enc_data = enc_data.replace('-', '+').replace('_', '/')
    n = len(enc_data) % 4
    if n:
        enc_data += "===="[n:]
    decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
    dec_text = decrypter.feed(base64.b64decode(enc_data))
    dec_text += decrypter.feed()
    data = json.loads(dec_text.decode('utf-8'))
    return data.get('file')


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
        headers['X-Requested-With'] = 'XMLHttpRequest'
        api_response = client.get(api_url, headers=headers, timeout=15)
        if not api_response or not api_response.text:
            return None

        data = api_response.json()
        sources = data.get('sources')
        if isinstance(sources, dict):
            file_url = sources.get('file')
            if file_url:
                data['sources'] = [{'file': file_url}]
        else:
            file_url = decrypt_megaplay_source(data.get('enc'))
            if file_url:
                data['sources'] = [{'file': file_url}]

        return data
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        control.log(f"MegaPlay extractor error: {e}", level='info')
        return None
    except Exception as e:
        control.log(f"MegaPlay extractor error: {e}", level='error')
        return None
