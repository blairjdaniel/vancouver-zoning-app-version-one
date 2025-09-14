import React, { useState } from 'react';

export default function KeyManager() {
  const [openai, setOpenai] = useState('');
  const [yelp, setYelp] = useState('');
  const [status, setStatus] = useState(null);

  const handleSubmit = async () => {
    setStatus('saving');
    try {
      const res = await fetch('/api/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ openai_key: openai, yelp_key: yelp })
      });
      const j = await res.json();
      if (j.success) {
        setStatus('saved');
      } else {
        setStatus('error');
      }
    } catch (e) {
      console.error(e);
      setStatus('error');
    }
  };

  const pasteFromClipboard = async (setter) => {
    try {
      const text = await navigator.clipboard.readText();
      setter(text.trim());
    } catch (e) {
      console.error('clipboard error', e);
    }
  };

  return (
    <div style={{ padding: 16, background: '#fff', borderRadius: 8 }}>
      <h3>API Keys</h3>
      <p>Paste your OpenAI and Yelp API keys here. The app will store them securely when possible.</p>
      <div style={{ marginBottom: 8 }}>
        <label>OpenAI API Key</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={openai} onChange={e => setOpenai(e.target.value)} style={{ flex: 1 }} />
          <button onClick={() => pasteFromClipboard(setOpenai)}>Paste</button>
        </div>
      </div>
      <div style={{ marginBottom: 8 }}>
        <label>Yelp API Key</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={yelp} onChange={e => setYelp(e.target.value)} style={{ flex: 1 }} />
          <button onClick={() => pasteFromClipboard(setYelp)}>Paste</button>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <button onClick={handleSubmit}>Save keys</button>
        {status === 'saving' && <span style={{ marginLeft: 8 }}>Saving…</span>}
        {status === 'saved' && <span style={{ marginLeft: 8, color: 'green' }}>Saved</span>}
        {status === 'error' && <span style={{ marginLeft: 8, color: 'red' }}>Error</span>}
      </div>
    </div>
  );
}
