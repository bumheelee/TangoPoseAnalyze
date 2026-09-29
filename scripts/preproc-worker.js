self.onmessage = async (ev) => {
  const msg = ev.data;
  if (msg.type === 'init') {
    // create an offscreen canvas once
    self._canvas = new OffscreenCanvas(msg.width || 2, msg.height || 2);
    self._ctx = self._canvas.getContext('2d');
    return;
  }
  if (msg.type === 'downscale' && msg.ib) {
    try {
      const { ib, dw, dh } = msg;
      self._canvas.width = dw; self._canvas.height = dh;
      self._ctx.clearRect(0,0,dw,dh);
      self._ctx.drawImage(ib, 0, 0, dw, dh);
      // produce a new ImageBitmap to send back
      const out = self._canvas.transferToImageBitmap();
      // close incoming bitmap if transferable
      try { ib.close && ib.close(); } catch (e) {}
      self.postMessage({ type: 'downscaled', ib: out }, [out]);
    } catch (e) {
      self.postMessage({ type: 'error', message: String(e) });
    }
  }
};
