#!/usr/bin/env python3
"""CLI helper to set API keys for the app.

Usage:
  python3 scripts/set_env.py --openai <KEY> --yelp <KEY>

This sets keys in the OS keyring when available, otherwise writes to backend/.env.
"""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / 'backend' / '.env'


def set_in_env(kv):
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, 'r') as f:
            lines = [l.rstrip('\n') for l in f.readlines() if l.strip()]
    current = { }
    for l in lines:
        if '=' in l:
            a, b = l.split('=', 1)
            current[a] = b
    current.update(kv)
    with open(ENV_PATH, 'w') as f:
        for k, v in current.items():
            f.write(f"{k}={v}\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--openai', help='OpenAI API key')
    p.add_argument('--yelp', help='Yelp API key')
    args = p.parse_args()

    use_keyring = False
    try:
        import keyring
        use_keyring = True
    except Exception:
        use_keyring = False

    kv = {}
    if args.openai:
        if use_keyring:
            try:
                keyring.set_password('vancouver_zoning_app', 'OPENAI_API_KEY', args.openai)
                kv['OPENAI_API_KEY'] = '<stored-in-keyring>'
            except Exception:
                kv['OPENAI_API_KEY'] = args.openai
        else:
            kv['OPENAI_API_KEY'] = args.openai
    if args.yelp:
        if use_keyring:
            try:
                keyring.set_password('vancouver_zoning_app', 'YELP_API_KEY', args.yelp)
                kv['YELP_API_KEY'] = '<stored-in-keyring>'
            except Exception:
                kv['YELP_API_KEY'] = args.yelp
        else:
            kv['YELP_API_KEY'] = args.yelp

    if kv:
        set_in_env(kv)
        print('Updated backend/.env (or stored in keyring).')
    else:
        print('No keys provided.')


if __name__ == '__main__':
    main()
