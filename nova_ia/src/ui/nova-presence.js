/* Procedural NOVA presence. No images, network requests or extra dependencies. */
(() => {
  const chat = document.getElementById('aba-chat');
  const presence = document.getElementById('nova-presence');
  const messages = document.getElementById('chat-msgs');
  const canvas = document.getElementById('nova-orb-canvas');
  const status = document.getElementById('nova-presence-status');
  const ctx = canvas.getContext('2d');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let frame = 0, time = 0, last = 0, state = 'idle';
  const labels = { idle: 'Estou aqui. Pode falar.', listening: 'Estou ouvindo…', thinking: 'Um instante, estou pensando…', speaking: 'Falando com você…' };

  function sync() {
    chat.classList.toggle('conversation-empty', !messages.querySelector('.msg'));
    state = gravandoVoz ? 'listening'
      : messages.querySelector('#typing-msg, #streaming-bubble') ? 'thinking'
      : window.speechSynthesis?.speaking ? 'speaking' : 'idle';
    presence.dataset.state = state;
    if (status.textContent !== labels[state]) status.textContent = labels[state];
    restart();
  }

  function draw() {
    const size = canvas.clientWidth;
    if (!size || !ctx) return;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const pixels = Math.round(size * dpr);
    if (canvas.width !== pixels) canvas.width = canvas.height = pixels;
    ctx.setTransform(pixels / 400, 0, 0, pixels / 400, 0, 0);
    ctx.clearRect(0, 0, 400, 400);
    ctx.translate(200, 200);
    const energy = state === 'idle' ? .25 : state === 'thinking' ? .65 : 1;
    const breath = 1 + Math.sin(time * (state === 'idle' ? .8 : 2.6)) * .014 * energy;
    ctx.scale(breath, breath);
    const halo = ctx.createRadialGradient(0, 0, 60, 0, 0, 190);
    halo.addColorStop(0, 'rgba(90,45,190,0)');
    halo.addColorStop(.5, 'rgba(117,64,220,.12)');
    halo.addColorStop(1, 'rgba(100,50,210,0)');
    ctx.fillStyle = halo; ctx.fillRect(-200, -200, 400, 400);
    ctx.rotate(-.48 + Math.sin(time * .19) * .045);

    // The back half of the accretion disk disappears behind the dark core.
    function disk(front) {
      ctx.save(); ctx.globalCompositeOperation = 'screen';
      for (let j = 0; j < 48; j++) {
        const radius = 106 + j * 1.08;
        const start = front ? 0 : Math.PI;
        ctx.beginPath();
        for (let i = 0; i <= 110; i++) {
          const a = start + i / 110 * Math.PI;
          const ripple = Math.sin(a * 3 + time * .7 + j * .12) * (2 + energy);
          const x = Math.cos(a) * (radius + ripple);
          const y = Math.sin(a) * (radius * .39 + ripple) + Math.sin(a * 2 + time * .4) * 3;
          if (!i) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        const gradient = ctx.createLinearGradient(-155, -50, 155, 60);
        const alpha = (.12 + Math.pow(Math.sin(j * .43 + time * .35), 8) * .7) * (1 - j / 85);
        gradient.addColorStop(0, `rgba(95,202,244,${alpha})`);
        gradient.addColorStop(.3, `rgba(172,124,255,${alpha})`);
        gradient.addColorStop(.56, `rgba(233,199,255,${alpha})`);
        gradient.addColorStop(.8, `rgba(121,71,246,${alpha})`);
        gradient.addColorStop(1, `rgba(83,223,233,${alpha})`);
        ctx.strokeStyle = gradient; ctx.lineWidth = j % 7 === 0 ? 1.2 : .65; ctx.stroke();
      }
      ctx.restore();
    }
    disk(false);
    const core = ctx.createRadialGradient(-26, -32, 4, 0, 0, 104);
    core.addColorStop(0, '#100b22'); core.addColorStop(.67, '#05040c');
    core.addColorStop(.88, '#120d2d'); core.addColorStop(.965, '#594095'); core.addColorStop(1, '#b9a4f1');
    ctx.shadowColor = '#8457ed'; ctx.shadowBlur = 18;
    ctx.fillStyle = core; ctx.beginPath(); ctx.arc(0, 0, 103, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
    // Fine lensing arcs give the silhouette a glass-like, dimensional edge.
    for (let j = 0; j < 10; j++) {
      ctx.beginPath(); ctx.ellipse(0, 0, 105 + j * 2.5, 103 + j * 1.7, .13, Math.PI * .93, Math.PI * 2.12);
      ctx.strokeStyle = `rgba(${j % 3 ? '171,131,243' : '133,227,246'},${.32 - j * .025})`;
      ctx.lineWidth = j === 1 ? 1.4 : .65; ctx.stroke();
    }
    disk(true);
  }

  function animate(now) {
    frame = 0;
    if (document.hidden || !presence.closest('.aba.active')) { last = 0; return; }
    if (last) time += Math.min((now - last) / 1000, .05) * (state === 'thinking' ? 1.8 : 1);
    last = now; draw();
    if (!reducedMotion.matches && settings.animations !== false) frame = requestAnimationFrame(animate);
  }
  function restart() {
    if (!frame && !document.hidden && presence.closest('.aba.active')) frame = requestAnimationFrame(animate);
  }
  new MutationObserver(sync).observe(messages, { childList: true, subtree: true });
  new MutationObserver(sync).observe(document.getElementById('chat-mic'), { attributes: true, attributeFilter: ['class'] });
  new MutationObserver(sync).observe(chat, { attributes: true, attributeFilter: ['class'] });
  new ResizeObserver(() => { draw(); restart(); }).observe(canvas);
  document.addEventListener('visibilitychange', restart);
  reducedMotion.addEventListener('change', restart);
  // Speech synthesis exposes state but no global start/end event.
  setInterval(() => { if (!document.hidden && presence.closest('.aba.active')) sync(); }, 250);
  sync();
})();
