#!/usr/bin/env python3
"""
Desktop launcher for Vancouver Zoning App.

Starts the backend (backend/app.py) in a subprocess, waits for the health
endpoint, then opens a pywebview window pointed at the local server.

Usage:
  python3 backend/desktop_app.py

During packaging with PyInstaller, include this file as the entrypoint.
"""
import subprocess
import sys
import time
import os
from pathlib import Path

try:
    import webview
except Exception:
    webview = None

ROOT = Path(__file__).resolve().parent
BACKEND_SCRIPT = ROOT / 'app.py'
PROJECT_ROOT = ROOT.parent
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', 5002))
URL = f"http://{HOST}:{PORT}"


ENV_PATH = ROOT / '.env'


def prompt_for_api_keys():
    """Prompt user for missing API keys and save to backend/.env"""
    # Only use tkinter when available; fallback to console input
    openai_key = os.getenv('OPENAI_API_KEY')
    yelp_key = os.getenv('YELP_API_KEY')

    if ENV_PATH.exists():
        # load existing keys
        try:
            with open(ENV_PATH, 'r') as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        if k == 'OPENAI_API_KEY' and not openai_key:
                            openai_key = v
                        if k == 'YELP_API_KEY' and not yelp_key:
                            yelp_key = v
        except Exception:
            pass

    if openai_key and yelp_key:
        return openai_key, yelp_key

    # Try a small first-run GUI form with tkinter. If tkinter isn't available
    # (or running in a headless environment), fall back to simpledialog or console.
    try:
        import tkinter as tk

        def show_first_run_window(existing_openai, existing_yelp):
            """Show a compact first-run form and return (openai_key, yelp_key).

            The form has Save and Skip buttons. Save writes values; Skip returns
            whatever was provided or None.
            """
            result = {'openai': existing_openai or '', 'yelp': existing_yelp or '', 'saved': False}

            root = tk.Tk()
            root.title('First run setup')
            # Keep window small and on top
            root.geometry('480x160')
            root.resizable(False, False)

            frm = tk.Frame(root, padx=12, pady=8)
            frm.pack(fill=tk.BOTH, expand=True)

            tk.Label(frm, text='OpenAI API Key (optional):').grid(row=0, column=0, sticky='w')
            openai_var = tk.StringVar(value=result['openai'])
            openai_entry = tk.Entry(frm, textvariable=openai_var, width=46, show='*')
            openai_entry.grid(row=0, column=1, pady=4, sticky='w')

            # Buttons to help non-technical users obtain/paste the key
            def open_openai_docs():
                import webbrowser
                webbrowser.open('https://platform.openai.com/account/api-keys')

            def paste_openai_from_clipboard():
                try:
                    val = root.clipboard_get().strip()
                    if val:
                        openai_var.set(val)
                except Exception:
                    pass

            btn_openai_get = tk.Button(frm, text='Get', width=6, command=open_openai_docs)
            btn_openai_get.grid(row=0, column=2, padx=6)
            btn_openai_paste = tk.Button(frm, text='Paste', width=6, command=paste_openai_from_clipboard)
            btn_openai_paste.grid(row=0, column=3)

            tk.Label(frm, text='Yelp API Key (optional):').grid(row=1, column=0, sticky='w')
            yelp_var = tk.StringVar(value=result['yelp'])
            yelp_entry = tk.Entry(frm, textvariable=yelp_var, width=46, show='*')
            yelp_entry.grid(row=1, column=1, pady=4, sticky='w')

            def open_yelp_docs():
                import webbrowser
                webbrowser.open('https://www.yelp.com/developers/documentation/v3/authentication')

            def paste_yelp_from_clipboard():
                try:
                    val = root.clipboard_get().strip()
                    if val:
                        yelp_var.set(val)
                except Exception:
                    pass

            btn_yelp_get = tk.Button(frm, text='Get', width=6, command=open_yelp_docs)
            btn_yelp_get.grid(row=1, column=2, padx=6)
            btn_yelp_paste = tk.Button(frm, text='Paste', width=6, command=paste_yelp_from_clipboard)
            btn_yelp_paste.grid(row=1, column=3)

            btn_frm = tk.Frame(frm)
            btn_frm.grid(row=2, column=0, columnspan=2, pady=(12, 0))

            def on_save():
                result['openai'] = openai_var.get().strip() or None
                result['yelp'] = yelp_var.get().strip() or None
                result['saved'] = True
                root.destroy()

            def on_skip():
                # leave values as-is (possibly empty)
                result['openai'] = openai_var.get().strip() or None
                result['yelp'] = yelp_var.get().strip() or None
                root.destroy()

            save_btn = tk.Button(btn_frm, text='Save and Continue', command=on_save)
            save_btn.pack(side=tk.LEFT, padx=8)
            skip_btn = tk.Button(btn_frm, text='Skip', command=on_skip)
            skip_btn.pack(side=tk.LEFT, padx=8)

            # Focus the first entry
            openai_entry.focus_set()
            try:
                root.attributes('-topmost', True)
            except Exception:
                pass

            root.mainloop()
            return result['openai'], result['yelp']

        openai_key, yelp_key = show_first_run_window(openai_key, yelp_key)
    except Exception:
        # Try simpledialog if tkinter root creation failed, otherwise console
        try:
            import tkinter as tk
            from tkinter import simpledialog

            root = tk.Tk()
            root.withdraw()
            if not openai_key:
                openai_key = simpledialog.askstring('API Key', 'Enter OpenAI API key (optional):')
            if not yelp_key:
                yelp_key = simpledialog.askstring('API Key', 'Enter Yelp API key (optional):')
            root.destroy()
        except Exception:
            # fallback to console
            if not openai_key:
                try:
                    openai_key = input('Enter OpenAI API key (or leave blank): ').strip() or None
                except Exception:
                    openai_key = None
            if not yelp_key:
                try:
                    yelp_key = input('Enter Yelp API key (or leave blank): ').strip() or None
                except Exception:
                    yelp_key = None

    # Prefer secure storage in the OS keyring when available, otherwise
    # persist keys to backend/.env (preserve other entries)
    use_keyring = False
    try:
        import keyring
        use_keyring = True
    except Exception:
        use_keyring = False

    if use_keyring:
        try:
            if openai_key:
                keyring.set_password('vancouver_zoning_app', 'OPENAI_API_KEY', openai_key)
            if yelp_key:
                keyring.set_password('vancouver_zoning_app', 'YELP_API_KEY', yelp_key)
        except Exception:
            # fall back to file if keyring fails
            use_keyring = False

    # Persist to .env only if keyring not used or failed
    try:
        lines = []
        if ENV_PATH.exists():
            with open(ENV_PATH, 'r') as f:
                lines = [l.rstrip('\n') for l in f.readlines() if l.strip()]

        # build dict
        kv = {}
        for l in lines:
            if '=' in l:
                k, v = l.split('=', 1)
                kv[k] = v

        # Ensure default keys exist so file is readable for the installer
        kv.setdefault('FLASK_ENV', 'production')
        kv.setdefault('FLASK_DEBUG', 'false')
        kv.setdefault('SECRET_KEY', 'vancouver-zoning-secret-key-2025')
        kv.setdefault('APP_PORT', str(PORT))
        kv.setdefault('MUNICIPALITY', 'vancouver')
        kv.setdefault('OPENAI_MODEL', 'gpt-4')
        kv.setdefault('DALLE_MODEL', 'dall-e-3')

        if not use_keyring:
            if openai_key:
                kv['OPENAI_API_KEY'] = openai_key
            else:
                # ensure blank placeholder present
                kv.setdefault('OPENAI_API_KEY', '')
            if yelp_key:
                kv['YELP_API_KEY'] = yelp_key
            else:
                kv.setdefault('YELP_API_KEY', '')
        else:
            # store placeholders to indicate keyring is used
            kv.setdefault('OPENAI_API_KEY', '<stored-in-keyring>')
            kv.setdefault('YELP_API_KEY', '<stored-in-keyring>')

        with open(ENV_PATH, 'w') as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        print(f"Failed to write .env: {e}")

    return openai_key, yelp_key


def start_backend():
    """Start the backend as a detached subprocess."""
    if not BACKEND_SCRIPT.exists():
        print(f"Backend script not found: {BACKEND_SCRIPT}")
        sys.exit(1)

    # Use module execution so `import backend.*` resolves (run from project root)
    cmd = [sys.executable, '-m', 'backend.app']
    env = os.environ.copy()

    # Ensure we run with the project root as working directory
    proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc


def wait_for_health(timeout=30):
    """Poll the /api/health endpoint until it returns 200 or timeout."""
    import requests

    start = time.time()
    url = f"{URL}/api/ai/status"  # health/status endpoint present
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    # Prompt for keys and ensure they are saved before starting backend
    openai_key, yelp_key = prompt_for_api_keys()

    # Ensure keys are present in the current environment and will be passed to the subprocess
    if openai_key:
        os.environ['OPENAI_API_KEY'] = openai_key
    if yelp_key:
        os.environ['YELP_API_KEY'] = yelp_key

    proc = start_backend()
    print("Starting backend, waiting for readiness...")

    ready = wait_for_health(timeout=40)
    if not ready:
        print("Backend did not become ready in time. Check logs.")
        # Print some of the backend output to help debugging
        try:
            out = proc.stdout.read().decode('utf-8', errors='ignore')
            print(out[:4000])
        except Exception:
            pass
        sys.exit(1)

    print(f"Backend ready at {URL}")

    if webview is None:
        print("pywebview not installed — opening in default browser instead.")
        import webbrowser
        webbrowser.open(URL)
        proc.wait()
        return

    # Open pywebview window
    webview.create_window('Vancouver Zoning App', URL, width=1200, height=800)
    webview.start()


if __name__ == '__main__':
    main()
