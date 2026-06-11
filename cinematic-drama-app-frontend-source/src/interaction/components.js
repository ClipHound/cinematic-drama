const asset = (path) => `./assets/${path}`;
const effectLiftCss = () => asset('app-overrides/effect-lift.css');

const eventMap = {
  celebrate_confetti: 'celebrate_click',
  anger_release: 'anger_tap',
  tear_resonance: 'tear_hold',
  laugh_burst: 'laugh_click',
  shatter_strike: 'emotion_burst_click',
  sugar_storm: 'sweet_tap',
  guardian_shield: 'shield_hold',
  team_cheer: 'team_choose',
  prediction_card: 'prediction_submit',
  clue_judge_card: 'clue_judge',
  episode_end_prediction: 'prediction_submit',
  emotion_buffer: 'emotion_buffer_enter',
};

export function renderInteraction(container, props) {
  container.__interactionCleanup?.();
  container.__interactionCleanup = null;
  container.innerHTML = '';
  const renderer = registry[props.interactionPoint.component] || UnknownInteraction;
  const cleanup = renderer(container, props);
  if (typeof cleanup === 'function') {
    container.__interactionCleanup = cleanup;
  }
}

export function clearInteraction(container) {
  container.__interactionCleanup?.();
  container.__interactionCleanup = null;
  container.innerHTML = '';
}

function emit(props, actionData = {}, eventType) {
  props.onInteract({
    eventType: eventType || eventMap[props.interactionPoint.component] || 'interaction',
    actionData,
  });
}

function createStage(container, props, manager, className, title, subtitle) {
  const node = document.createElement('section');
  node.className = `real-effect ${className}`;
  node.innerHTML = `
    <button class="real-close" type="button" aria-label="关闭互动">
      <span>×</span>
    </button>
    <div class="real-copy">
      <strong>${title || props.interactionPoint.title || props.interactionPoint.component}</strong>
      <span>${subtitle || props.interactionPoint.highlight_reason || ''}</span>
    </div>
    <div class="real-body"></div>
  `;
  const close = () => props.onDismiss('closed');
  node.querySelector('.real-close').addEventListener('click', close);
  manager?.addCleanup?.(() => node.querySelector('.real-close')?.removeEventListener('click', close));
  container.appendChild(node);
  return node.querySelector('.real-body');
}

function createOriginalStage(container, cssPath, extraCssPaths = []) {
  const host = document.createElement('section');
  host.className = 'original-effect-host';
  const shadow = host.attachShadow({ mode: 'open' });
  shadow.innerHTML = `
    <link rel="stylesheet" href="${cssPath}">
    ${extraCssPaths.map((path) => `<link rel="stylesheet" href="${path}">`).join('')}
    <style>
      :host {
        position: absolute;
        inset: 0;
        display: block;
        width: 100%;
        height: 100%;
        overflow: hidden;
        pointer-events: auto;
        touch-action: none;
        user-select: none;
      }
      .app-shell {
        width: 100%;
        height: 100%;
        min-height: 0 !important;
        display: block !important;
        overflow: hidden !important;
        background: transparent !important;
      }
      .effect-stage,
      .phone-screen,
      .phone-frame {
        width: 100% !important;
        max-width: none !important;
        height: 100% !important;
        min-height: 0 !important;
        aspect-ratio: auto !important;
        background: transparent !important;
        box-shadow: none !important;
        border-radius: 0 !important;
      }
      .effect-stage,
      .phone-frame {
        position: relative !important;
        overflow: hidden !important;
      }
      .phone-frame {
        background: transparent !important;
      }
      .stage-background,
      .scene-bg,
      .fallback-gradient,
      .video-dim,
      .background-image,
      .background-video,
      .phone-frame::before {
        display: none !important;
      }
    </style>
    <main class="app-shell">
      <section class="effect-stage"></section>
    </main>
  `;
  container.appendChild(host);
  return shadow.querySelector('.effect-stage');
}

function mountLottie(node, path, options = {}, manager) {
  if (!window.lottie || !node) return null;
  node.dataset.lottieId = crypto.randomUUID?.() || String(Date.now());
  node.__lottie?.destroy?.();
  node.__lottie = window.lottie.loadAnimation({
    container: node,
    renderer: 'svg',
    loop: Boolean(options.loop),
    autoplay: options.autoplay !== false,
    path,
    rendererSettings: {
      preserveAspectRatio: options.preserveAspectRatio || 'xMidYMid meet',
    },
  });
  manager?.addCleanup?.(() => node.__lottie?.destroy?.());
  return node.__lottie;
}

function CelebrateConfetti(container, props, manager) {
  const stage = createOriginalStage(container, asset('qingzhu-demo/src/styles/app.css'));
  stage.innerHTML = `
    <style>
      .lipao-animation,
      .lipao-animation svg {
        top: 0 !important;
        height: 100% !important;
        min-height: 100% !important;
        transform-origin: top center !important;
      }
    </style>
    <div class="lipao-animation" aria-hidden="true"></div>
    <div class="celebrate-widget">
      <button class="effect-close" type="button" aria-label="Close">
        <img src="${asset('qingzhu-demo/images/x.png')}" alt="" draggable="false" />
      </button>
      <button class="celebrate-trigger" type="button" aria-label="点击庆祝">
        <span class="cannon-motion">
          <img src="${asset('qingzhu-demo/images/tong-cutout.png')}" alt="" draggable="false" />
        </span>
        <span class="celebrate-label">点击庆祝</span>
      </button>
    </div>
  `;
  const animation = mountLottie(stage.querySelector('.lipao-animation'), asset('qingzhu-demo/videos/lipao.json'), {
    autoplay: false,
    preserveAspectRatio: 'xMidYMin slice',
  }, manager);
  let clickCount = 0;
  stage.querySelector('.effect-close').addEventListener('click', (event) => {
    event.stopPropagation();
    props.onDismiss('closed');
  });
  stage.querySelector('.celebrate-trigger').addEventListener('click', () => {
    clickCount += 1;
    animation?.goToAndPlay?.(0, true);
    stage.querySelector('.lipao-animation').classList.add('is-playing');
    stage.querySelector('.celebrate-trigger').classList.remove('is-shaking');
    requestAnimationFrame(() => stage.querySelector('.celebrate-trigger').classList.add('is-shaking'));
    emit(props, { click_count: clickCount, growth_level_reached: Math.min(3, clickCount) });
  });
}

function AngerRelease(container, props, manager) {
  const stage = createOriginalStage(container, asset('angry-demo/src/styles/app.css'));
  const EFFECT_DURATION = 620;
  const WORD_DURATION = 1300;
  const ANGER_WORDS = ['生气', '可恶'];
  let isAnimationActive = false;
  let isEffectDismissed = false;
  let isCloseVisible = true;
  let animation = null;
  let tapCount = 0;
  let angerTexts = [];
  let hitEffects = [];

  const hitEffectHTML = (effect) => `
    <div class="hit-effect" data-hit-id="${effect.id}" style="--hit-x:${effect.x}px;--hit-y:${effect.y}px;">
      <img class="strike-effect" src="${asset('angry-demo/images/texiao-cutout.png')}" alt="" draggable="false" />
      <img class="hand-effect" src="${asset('angry-demo/images/hand-cutout.png')}" alt="" draggable="false" />
    </div>
  `;
  const angerTextHTML = (item) => `
    <span
      class="anger-float-text"
      data-text-id="${item.id}"
      style="--word-x:${item.offsetX}px;--word-y:${item.offsetY}px;--word-drift-x:${item.driftX}px;--word-drift-y:${item.driftY}px;"
    >${item.label}</span>
  `;

  const renderAngry = () => {
    if (isEffectDismissed) {
      stage.innerHTML = '';
      return;
    }

    stage.innerHTML = `
      <div class="angry-cluster">
        <div class="angry-anchor ${isAnimationActive ? 'is-glowing' : ''}">
          ${!isAnimationActive ? `<img class="angry-image" src="${asset('angry-demo/images/angry.png')}" alt="" draggable="false" />` : ''}
          ${isAnimationActive ? '<div class="angry-lottie"></div>' : ''}
          ${isCloseVisible ? `
            <button class="close-effect" type="button" aria-label="关闭特效">
              <img src="${asset('angry-demo/images/x.png')}" alt="" draggable="false" />
            </button>
          ` : ''}
          <div class="anger-text-layer">
            ${angerTexts.map((item) => angerTextHTML(item)).join('')}
          </div>
        </div>
        <div class="angry-caption">
          <span class="caption-title" data-text="欺人太甚">欺人太甚</span>
          <span class="caption-subtitle"><span class="tap-icon"></span>点击人物泄愤</span>
        </div>
      </div>
      <div class="hit-layer" aria-hidden="true">
        ${hitEffects.map((effect) => hitEffectHTML(effect)).join('')}
      </div>
    `;

    stage.querySelector('.close-effect')?.addEventListener('click', handleCloseClick);

    if (isAnimationActive && !animation) {
      animation = mountLottie(stage.querySelector('.angry-lottie'), asset('angry-demo/videos/angry.json'), { autoplay: true }, manager);
      const handleComplete = () => {
        isAnimationActive = false;
        animation?.removeEventListener?.('complete', handleComplete);
        animation?.destroy?.();
        animation = null;
        renderAngry();
      };
      animation?.addEventListener?.('complete', handleComplete);
      manager?.addCleanup?.(() => animation?.removeEventListener?.('complete', handleComplete));
    }
  };

  const removeHitEffect = (effectId) => {
    hitEffects = hitEffects.filter((item) => item.id !== effectId);
    stage.querySelector(`[data-hit-id="${effectId}"]`)?.remove();
  };

  const removeAngerText = (textId) => {
    angerTexts = angerTexts.filter((item) => item.id !== textId);
    stage.querySelector(`[data-text-id="${textId}"]`)?.remove();
  };

  const handleStageClick = (event) => {
    if (isEffectDismissed || event.target.closest('.close-effect')) {
      return;
    }

    if (isCloseVisible) {
      isCloseVisible = false;
      stage.querySelector('.close-effect')?.remove();
    }

    const point = getLocalPoint(stage, event);
    const effect = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      x: point.x,
      y: point.y,
    };
    hitEffects = [...hitEffects, effect];
    const hitTimer = window.setTimeout(() => removeHitEffect(effect.id), EFFECT_DURATION);
    manager?.addCleanup?.(() => window.clearTimeout(hitTimer));

    const angerText = {
      id: `${effect.id}-word`,
      label: ANGER_WORDS[Math.floor(Math.random() * ANGER_WORDS.length)],
      offsetX: Math.round(Math.random() * 76 + 18),
      offsetY: Math.round((Math.random() - 0.5) * 78),
      driftX: Math.round(Math.random() * 32 + 18),
      driftY: Math.round(Math.random() * 34 + 42),
    };
    angerTexts = [...angerTexts.slice(-4), angerText];
    const wordTimer = window.setTimeout(() => removeAngerText(angerText.id), WORD_DURATION);
    manager?.addCleanup?.(() => window.clearTimeout(wordTimer));

    if (!isAnimationActive) {
      isAnimationActive = true;
      tapCount += 1;
      emit(props, { tap_count: tapCount, target_x: point.x, target_y: point.y }, 'anger_tap');
      renderAngry();
      return;
    }

    tapCount += 1;
    emit(props, { tap_count: tapCount, target_x: point.x, target_y: point.y }, 'anger_tap');
    stage.querySelector('.hit-layer')?.insertAdjacentHTML('beforeend', hitEffectHTML(effect));
    stage.querySelector('.anger-text-layer')?.insertAdjacentHTML('beforeend', angerTextHTML(angerText));
  };

  const handleCloseClick = (event) => {
    event.stopPropagation();
    isEffectDismissed = true;
    isCloseVisible = false;
    hitEffects = [];
    angerTexts = [];
    isAnimationActive = false;
    animation?.destroy?.();
    animation = null;
    props.onDismiss('closed');
    renderAngry();
  };

  stage.addEventListener('click', handleStageClick);
  manager?.addCleanup?.(() => {
    stage.removeEventListener('click', handleStageClick);
    animation?.destroy?.();
  });

  renderAngry();
}

function TearResonance(container, props, manager) {
  const stage = createOriginalStage(container, asset('gandong-demo/src/styles/app.css'));
  let isEffectVisible = true;
  let isCloseVisible = true;
  let isHolding = false;
  let animation = null;
  let floatingTimer = null;
  let holdStartedAt = 0;

  const createFloatingText = () => {
    const words = ['emo', '难过', '呜呜'];
    const side = Math.random() > 0.5 ? 1 : -1;
    return {
      label: words[Math.floor(Math.random() * words.length)],
      startX: Math.round(58 + Math.random() * 84),
      startY: Math.round((Math.random() - 0.5) * 160),
      driftX: Math.round(side * (28 + Math.random() * 62)),
      driftY: Math.round(72 + Math.random() * 92),
      rotate: Math.round((Math.random() - 0.5) * 18),
      size: Math.round(13 + Math.random() * 5),
    };
  };

  const addTextBurst = () => {
    const layer = stage.querySelector('.floating-text-layer');
    if (!layer || !isEffectVisible) return;
    const burstCount = Math.random() > 0.68 ? 2 : 1;
    const burst = Array.from({ length: burstCount }, createFloatingText);
    burst.forEach((item) => {
      const node = document.createElement('span');
      node.className = 'floating-text';
      node.textContent = item.label;
      node.style.setProperty('--start-x', `${item.startX}px`);
      node.style.setProperty('--start-y', `${item.startY}px`);
      node.style.setProperty('--drift-x', `${item.driftX}px`);
      node.style.setProperty('--drift-y', `${item.driftY}px`);
      node.style.setProperty('--rotate', `${item.rotate}deg`);
      node.style.fontSize = `${item.size}px`;
      layer.appendChild(node);
      const timer = window.setTimeout(() => node.remove(), 2100);
      manager?.addCleanup?.(() => window.clearTimeout(timer));
    });
  };

  const stopFloatingTimer = () => {
    window.clearInterval(floatingTimer);
    floatingTimer = null;
  };

  const renderGandong = () => {
    if (!isEffectVisible) {
      stage.innerHTML = '';
      return;
    }

    stage.innerHTML = `
      <div class="blue-haze" aria-hidden="true"></div>
      <div class="effect-anchor">
        ${isCloseVisible ? `
          <button class="close-effect" type="button" aria-label="关闭特效">
            <img src="${asset('gandong-demo/images/x.png')}" alt="" draggable="false" />
          </button>
        ` : ''}

        <button
          class="emo-trigger ${isHolding ? 'is-holding' : ''}"
          type="button"
          aria-label="按住释放 emo"
        >
          <span class="effect-visual">
            ${!isHolding ? `<img src="${asset('gandong-demo/images/gandong.png')}" alt="" draggable="false" />` : ''}
            ${isHolding ? '<span class="inline-lottie"></span>' : ''}
          </span>
          <span class="trigger-copy">
            <span>难过</span>
            <span>按住释放emo</span>
          </span>
        </button>
      </div>
      <div class="floating-text-layer" aria-hidden="true"></div>
    `;

    const closeButton = stage.querySelector('.close-effect');
    closeButton?.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
    closeButton?.addEventListener('click', dismissEffect);

    const trigger = stage.querySelector('.emo-trigger');
    trigger?.addEventListener('pointerdown', startHolding);
    trigger?.addEventListener('pointerup', stopHolding);
    trigger?.addEventListener('pointercancel', stopHolding);
    trigger?.addEventListener('pointerleave', stopHolding);
    trigger?.addEventListener('keydown', (event) => {
      if (event.key === ' ' || event.key === 'Enter') startHolding(event);
    });
    trigger?.addEventListener('keyup', (event) => {
      if (event.key === ' ' || event.key === 'Enter') stopHolding();
    });

    if (isHolding) {
      animation?.destroy?.();
      animation = mountLottie(stage.querySelector('.inline-lottie'), asset('gandong-demo/videos/kusu.json'), { loop: true, autoplay: true }, manager);
    }
  };

  const startHolding = (event) => {
    event?.preventDefault?.();
    if (!isEffectVisible || isHolding) return;
    isCloseVisible = false;
    isHolding = true;
    holdStartedAt = performance.now();
    renderGandong();
    addTextBurst();
    stopFloatingTimer();
    floatingTimer = window.setInterval(addTextBurst, 520);
  };

  const stopHolding = () => {
    if (!isHolding) return;
    const duration = Math.round(performance.now() - holdStartedAt);
    isHolding = false;
    animation?.destroy?.();
    animation = null;
    stopFloatingTimer();
    emit(props, { hold_duration_ms: duration, resonance_level: Math.min(100, Math.round(duration / 22)) }, 'tear_hold');
    renderGandong();
  };

  const dismissEffect = (event) => {
    event?.stopPropagation?.();
    isEffectVisible = false;
    isCloseVisible = false;
    isHolding = false;
    animation?.destroy?.();
    animation = null;
    stopFloatingTimer();
    props.onDismiss('closed');
    renderGandong();
  };

  manager?.addCleanup?.(() => {
    animation?.destroy?.();
    stopFloatingTimer();
  });

  renderGandong();
}

function LaughBurst(container, props, manager) {
  const stage = createOriginalStage(container, asset('laugh-demo/src/styles/app.css'));
  let isAnimationActive = false;
  let isEffectDismissed = false;
  let playCount = 0;
  let animation = null;

  const renderLaugh = () => {
    if (isEffectDismissed) {
      stage.innerHTML = '';
      return;
    }

    stage.innerHTML = `
      <div class="effect-anchor">
        <button
          class="laugh-trigger ${isAnimationActive ? 'is-active' : ''}"
          type="button"
          aria-label="${isAnimationActive ? 'Show laugh text' : 'Play laugh animation'}"
        >
          ${!isAnimationActive ? `<img src="${asset('laugh-demo/images/laugh.png')}" alt="" draggable="false" />` : ''}
          ${isAnimationActive ? '<span class="inline-lottie" aria-hidden="true"></span>' : ''}
        </button>

        ${!isAnimationActive ? `
          <button class="close-effect" type="button" aria-label="Close laugh effect">
            <img src="${asset('laugh-demo/images/x.png')}" alt="" draggable="false" />
          </button>
        ` : ''}

        ${!isAnimationActive ? '<span class="tap-hint">点击</span>' : ''}
      </div>
      <div class="floating-text-layer" aria-hidden="true"></div>
    `;

    stage.querySelector('.laugh-trigger')?.addEventListener('click', handleEffectClick);
    stage.querySelector('.close-effect')?.addEventListener('click', dismissAllEffects);

    if (isAnimationActive) {
      playCount = 1;
      const lottieNode = stage.querySelector('.inline-lottie');
      animation?.destroy?.();
      animation = mountLottie(lottieNode, asset('laugh-demo/videos/emojiTest.json'), { autoplay: true }, manager);
      const dismissEffect = () => {
        if (playCount < 2) {
          playCount += 1;
          animation?.goToAndPlay?.(0, true);
          return;
        }

        stage.querySelector('.floating-text-layer')?.replaceChildren();
        isAnimationActive = false;
        isEffectDismissed = true;
        emit(props, { click_count: clickCount, auto_dismissed: true }, 'laugh_click');
        props.onDismiss('completed');
      };
      animation?.addEventListener?.('complete', dismissEffect);
      manager?.addCleanup?.(() => animation?.removeEventListener?.('complete', dismissEffect));
    }
  };

  let clickCount = 0;
  const handleEffectClick = () => {
    if (isEffectDismissed) {
      return;
    }

    if (!isAnimationActive) {
      isAnimationActive = true;
      clickCount += 1;
      emit(props, { click_count: clickCount, started_animation: true }, 'laugh_click');
      renderLaugh();
      return;
    }

    clickCount += 1;
    const layer = stage.querySelector('.floating-text-layer');
    const labels = ['哈哈', '笑不活了'];
    const burst = labels.map((label, index) => ({
      id: `${Date.now()}-${index}`,
      label,
      offsetX: Math.round((Math.random() - 0.5) * 96),
      offsetY: Math.round(Math.random() * 42),
      delay: index * 90,
    }));

    burst.forEach((item) => {
      const node = document.createElement('span');
      node.className = 'floating-text';
      node.textContent = item.label;
      node.style.setProperty('--float-x', `${item.offsetX}px`);
      node.style.setProperty('--float-y', `${item.offsetY}px`);
      node.style.animationDelay = `${item.delay}ms`;
      layer.appendChild(node);
      const timer = window.setTimeout(() => node.remove(), 1800);
      manager?.addCleanup?.(() => window.clearTimeout(timer));
    });

    emit(props, { click_count: clickCount, floating_text_count: burst.length }, 'laugh_click');
  };

  const dismissAllEffects = (event) => {
    event?.stopPropagation?.();
    stage.querySelector('.floating-text-layer')?.replaceChildren();
    isAnimationActive = false;
    isEffectDismissed = true;
    animation?.destroy?.();
    props.onDismiss('closed');
    renderLaugh();
  };

  renderLaugh();
}

function ShatterStrike(container, props, manager) {
  const frames = [
    '01_keyframe_micro_stress.png',
    '02_keyframe_small_impact.png',
    '03_keyframe_radial_cracks.png',
    '04_keyframe_first_stress_ring.png',
    '06_keyframe_full_shatter.png',
    '07_keyframe_near_full_shatter.png',
    '08_keyframe_advanced_fracture.png',
  ];
  const stage = createOriginalStage(container, asset('crack-demo/src/styles/app.css'));
  stage.innerHTML = `
    <style>
      .crack-layer .crack-trigger-wrap {
        left: -4px !important;
        top: 54% !important;
        transform: translateY(-50%) !important;
      }
      .crack-layer .crack-count {
        left: 4px !important;
        top: calc(54% + 34px) !important;
        transform: none !important;
        text-align: left !important;
      }
    </style>
    <div class="crack-interaction crack-layer">
      <div class="crack-trigger-wrap">
        <span class="crack-button-pulse"></span>
        <button class="crack-trigger" type="button">点击释放爽感</button>
      </div>
      <div class="crack-count">暴击 0/${frames.length}</div>
      <div class="crack-effects"></div>
    </div>
  `;
  let count = 0;
  stage.querySelector('.crack-trigger').addEventListener('click', () => {
    count = Math.min(frames.length, count + 1);
    stage.querySelector('.crack-count').textContent = `暴击 ${count}/${frames.length}`;
    stage.querySelector('.crack-effects').innerHTML = `<img class="crack-frame-image" src="${asset(`crack-demo/effects/crack/cracked_glass_keyframes_ordered/${frames[count - 1]}`)}" alt="" />`;
    stage.querySelector('.crack-layer').classList.remove('is-shaking');
    requestAnimationFrame(() => stage.querySelector('.crack-layer').classList.add('is-shaking'));
    if (count >= frames.length && !stage.querySelector('.shuang-badge')) {
      stage.querySelector('.crack-layer').insertAdjacentHTML('beforeend', `<img class="shuang-badge" src="${asset('crack-demo/effects/crack/cracked_glass_keyframes_ordered/shuang-badge-transparent.png')}" alt="" />`);
    }
    emit(props, { click_count: count, crack_level: count, growth_level_reached: Math.min(3, Math.ceil(count / 2)) });
  });
}

function SugarStorm(container, props) {
  const HEART_ASSETS = [
    asset('sweet-demo/effects/sweet/heart-glossy.svg'),
    asset('sweet-demo/effects/sweet/heart-bubble.svg'),
    asset('sweet-demo/effects/sweet/heart-sparkle.svg'),
  ];
  const stage = createOriginalStage(container, asset('sweet-demo/src/styles/app.css'));
  const MAX_SWEET_LEVEL = 100;
  const MAX_PARTICLES = 45;
  let sweetLevel = 0;
  let particles = [];
  let isButtonBouncing = false;
  let showEffectClose = true;
  let isEffectDismissed = false;
  let decayTimer = 0;
  let decayInterval = 0;
  let bounceTimer = 0;
  let particleTimers = [];
  let tapCount = 0;
  let hasRendered = false;

  const randomBetween = (min, max) => Number((min + Math.random() * (max - min)).toFixed(2));
  const getHeartCount = (level) => {
    if (level >= 100) return 15;
    if (level >= 80) return 10;
    if (level >= 50) return 7;
    if (level >= 20) return 4;
    return 2;
  };
  const getSweetStage = (level) => {
    if (level >= 80) return 'sweet-burst';
    if (level >= 50) return 'sweet-high';
    if (level >= 20) return 'sweet-mid';
    return 'sweet-low';
  };
  const getGlowChance = (level) => {
    if (level >= 80) return 0.65;
    if (level >= 50) return 0.5;
    if (level >= 20) return 0.35;
    return 0.2;
  };
  const createHeartParticle = (level) => ({
    id: crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`,
    src: HEART_ASSETS[Math.floor(Math.random() * HEART_ASSETS.length)],
    left: randomBetween(5, 95),
    bottom: randomBetween(8, 38),
    size: Math.round(randomBetween(12, 36)),
    drift: Math.round(randomBetween(-35, 35)),
    rise: Math.round(randomBetween(260, 420)),
    opacity: randomBetween(0.45, 0.95),
    duration: randomBetween(3.5, 5.5),
    delay: randomBetween(0, 0.4),
    rotate: Math.round(randomBetween(-25, 25)),
    glow: Math.random() < getGlowChance(level),
  });
  const clearDecay = () => {
    window.clearTimeout(decayTimer);
    window.clearInterval(decayInterval);
    decayTimer = 0;
    decayInterval = 0;
  };
  const cleanupParticles = () => {
    particleTimers.forEach((timerId) => window.clearTimeout(timerId));
    particleTimers = [];
  };
  const cleanup = () => {
    clearDecay();
    window.clearTimeout(bounceTimer);
    cleanupParticles();
  };
  const renderParticles = () => particles.map((particle) => `
    <img
      alt=""
      data-particle-id="${particle.id}"
      class="heart-particle-img ${particle.glow ? 'glow' : ''}"
      src="${particle.src}"
      style="
        left:${particle.left}%;
        bottom:${particle.bottom}%;
        width:${particle.size}px;
        height:${particle.size}px;
        --rise:${particle.rise}px;
        --drift:${particle.drift}px;
        --rotate:${particle.rotate}deg;
        --duration:${particle.duration}s;
        --delay:${particle.delay}s;
        --opacity:${particle.opacity};
      "
    />
  `).join('');
  const appendParticleNodes = (newParticles) => {
    const layer = stage.querySelector('.heart-particles');
    if (!layer) return;
    newParticles.forEach((particle) => {
      const item = document.createElement('img');
      item.alt = '';
      item.dataset.particleId = particle.id;
      item.className = `heart-particle-img ${particle.glow ? 'glow' : ''}`;
      item.src = particle.src;
      item.style.left = `${particle.left}%`;
      item.style.bottom = `${particle.bottom}%`;
      item.style.width = `${particle.size}px`;
      item.style.height = `${particle.size}px`;
      item.style.setProperty('--rise', `${particle.rise}px`);
      item.style.setProperty('--drift', `${particle.drift}px`);
      item.style.setProperty('--rotate', `${particle.rotate}deg`);
      item.style.setProperty('--duration', `${particle.duration}s`);
      item.style.setProperty('--delay', `${particle.delay}s`);
      item.style.setProperty('--opacity', particle.opacity);
      layer.appendChild(item);
    });
  };
  const syncSweetDom = (sweetStage, isBurst) => {
    const filter = stage.querySelector('.sweet-pink-filter');
    const layer = stage.querySelector('.heart-particles');
    const indicator = stage.querySelector('.sweet-level-indicator');
    const interaction = stage.querySelector('.sweet-interaction');
    const button = stage.querySelector('.sweet-button');
    if (!filter || !layer || !indicator || !interaction || !button) return false;
    filter.className = `sweet-pink-filter ${sweetStage}`;
    filter.style.setProperty('--sweet-ratio', sweetLevel / 100);
    layer.className = `heart-particles ${sweetStage}`;
    indicator.textContent = `甜蜜度 ${sweetLevel}%`;
    interaction.classList.toggle('is-burst', isBurst);
    button.classList.toggle('is-bouncing', isButtonBouncing);
    button.style.setProperty('--sweet-power', sweetLevel / 100);
    const mainText = stage.querySelector('.sweet-main-text');
    if (mainText) mainText.textContent = isBurst ? '甜度爆发' : '连续点击，甜度升级';
    if (!showEffectClose) {
      stage.querySelector('.sweet-close-button')?.remove();
    }
    return true;
  };
  const renderSweet = () => {
    if (isEffectDismissed) {
      stage.innerHTML = '';
      return;
    }

    const sweetStage = getSweetStage(sweetLevel);
    const isBurst = sweetLevel >= 100;
    if (hasRendered && syncSweetDom(sweetStage, isBurst)) {
      return;
    }

    stage.innerHTML = `
      <section class="phone-frame phone-frame-sweet">
        <div class="sweet-pink-filter ${sweetStage}" style="--sweet-ratio:${sweetLevel / 100}"></div>
        <div class="heart-particles ${sweetStage}" aria-hidden="true">${renderParticles()}</div>
        <div class="sweet-level-indicator">甜蜜度 ${sweetLevel}%</div>
        <div class="player-ui effect-only-ui">
          <div class="sweet-interaction ${isBurst ? 'is-burst' : ''}">
            ${showEffectClose ? `
              <button aria-label="关闭撒糖特效" class="effect-close-button sweet-close-button" type="button">
                <img src="${asset('sweet-demo/effects/sweet/x.png')}" alt="" draggable="false" />
              </button>
            ` : ''}
            <button
              class="sweet-button ${isButtonBouncing ? 'is-bouncing' : ''}"
              style="--sweet-power:${sweetLevel / 100}"
              type="button"
            >
              <span class="tap-heart-icon" aria-hidden="true">
                <svg viewBox="0 0 44 44" role="presentation">
                  <path
                    class="tap-heart"
                    d="M28.5 6.5c-2.6 0-4.8 1.3-6.5 3.5-1.7-2.2-3.9-3.5-6.5-3.5C11.1 6.5 8 9.9 8 14.2c0 6.3 7.1 10.7 14 16.4 6.9-5.7 14-10.1 14-16.4 0-4.3-3.1-7.7-7.5-7.7Z"
                  ></path>
                  <path
                    class="tap-finger"
                    d="M15.9 25.5v-7.1c0-1.1.8-1.9 1.9-1.9s1.9.8 1.9 1.9v5.4l1.5-1c.7-.5 1.7-.4 2.3.2l4.8 4.9c.7.8.8 2 .2 2.9l-2.8 4.3c-.9 1.4-2.4 2.2-4 2.2h-5.2c-1.3 0-2.6-.6-3.4-1.6l-4.2-5.2c-.7-.9-.6-2.1.2-2.8.8-.7 2-.7 2.8.1l4 3.8v-6.1Z"
                  ></path>
                </svg>
              </span>
              <span class="sweet-button-copy">
                <span class="sweet-main-text">${isBurst ? '甜度爆发' : '连续点击，甜度升级'}</span>
                <span class="sweet-sub-text">让TA感受到你的心意</span>
              </span>
            </button>
          </div>
        </div>
      </section>
    `;
    hasRendered = true;
    stage.querySelector('.sweet-close-button')?.addEventListener('click', handleCloseClick);
    stage.querySelector('.sweet-button')?.addEventListener('click', handleSweetClick);
  };
  const removeParticle = (particleId, timerId) => {
    particles = particles.filter((item) => item.id !== particleId);
    particleTimers = particleTimers.filter((savedTimerId) => savedTimerId !== timerId);
    stage.querySelector(`[data-particle-id="${particleId}"]`)?.remove();
  };
  const startSweetDecay = () => {
    clearDecay();
    decayTimer = window.setTimeout(() => {
      decayInterval = window.setInterval(() => {
        sweetLevel = Math.max(0, sweetLevel - 10);
        if (sweetLevel === 0) {
          window.clearInterval(decayInterval);
          decayInterval = 0;
        }
        renderSweet();
      }, 500);
    }, 1000);
  };
  const triggerButtonBounce = () => {
    window.clearTimeout(bounceTimer);
    isButtonBouncing = false;
    renderSweet();
    window.requestAnimationFrame(() => {
      isButtonBouncing = true;
      renderSweet();
      bounceTimer = window.setTimeout(() => {
        isButtonBouncing = false;
        renderSweet();
      }, 260);
    });
  };
  function handleSweetClick() {
    showEffectClose = false;
    tapCount += 1;
    const nextSweetLevel = Math.min(MAX_SWEET_LEVEL, sweetLevel + 10);
    const newParticles = Array.from({ length: getHeartCount(nextSweetLevel) }, () => createHeartParticle(nextSweetLevel));
    const combinedParticles = [...particles, ...newParticles];
    const removedParticles = combinedParticles.slice(0, Math.max(0, combinedParticles.length - MAX_PARTICLES));
    sweetLevel = nextSweetLevel;
    particles = combinedParticles.slice(-MAX_PARTICLES);
    removedParticles.forEach((particle) => stage.querySelector(`[data-particle-id="${particle.id}"]`)?.remove());
    renderSweet();
    appendParticleNodes(newParticles);
    newParticles.forEach((particle) => {
      const life = (particle.duration + particle.delay) * 1000 + 300;
      const timerId = window.setTimeout(() => removeParticle(particle.id, timerId), life);
      particleTimers.push(timerId);
    });
    emit(props, {
      tap_count: tapCount,
      sweet_level: sweetLevel,
      growth_level_reached: Math.min(3, Math.ceil(sweetLevel / 34)),
    });
    triggerButtonBounce();
    startSweetDecay();
  }
  function handleCloseClick(event) {
    event.stopPropagation();
    isEffectDismissed = true;
    showEffectClose = false;
    sweetLevel = 0;
    particles = [];
    cleanup();
    props.onDismiss('closed');
  }

  renderSweet();
  return cleanup;
}

function GuardianShield(container, props, manager) {
  const stage = createOriginalStage(
    container,
    asset('guard-demo/src/styles/app.css'),
    [asset('guard-demo/src/components/ShieldEffect.css'), effectLiftCss()],
  );
  const CHARGE_DURATION = 2000;
  const SUCCESS_HOLD = 1000;
  const FLOATING_WORDS = ['加油', '为你守护'];
  let isPressing = false;
  let isVisible = true;
  let isExiting = false;
  let isFinished = false;
  let showClose = true;
  let success = false;
  let progress = 0;
  let startedAt = 0;
  let frameId = 0;
  let successTimer = 0;
  let floatingTimer = 0;
  let animation = null;
  let nextTextId = 0;
  let floatingTexts = [];

  const renderGuard = () => {
    if (isFinished) {
      stage.innerHTML = '';
      return;
    }

    const clampedProgress = Math.max(0, Math.min(progress, 1));
    const active = isVisible && !isExiting;
    const showLottie = active && clampedProgress > 0 && !success;
    stage.innerHTML = `
      <div
        class="shield-effect ${active ? 'is-active' : 'is-exiting'} ${success ? 'is-success' : ''}"
        style="--progress:${clampedProgress}"
        aria-hidden="true"
      >
        ${showLottie ? '<div class="lottie-effect"></div>' : ''}
        ${floatingTexts.map((item) => `
          <span
            class="floating-word"
            style="--float-x:${item.x}px;--float-y:${item.y}px;--float-drift:${item.drift}px"
          >${item.text}</span>
        `).join('')}
        <img class="center-shield" src="${asset('guard-demo/images/guard.png')}" alt="" />
        <div class="shield-label">${success ? '守护成功' : '长按守护'}</div>
      </div>

      ${showClose && !success ? `
        <button class="shield-close-button" type="button" aria-label="关闭守护">
          <img src="${asset('guard-demo/images/x.png')}" alt="" />
        </button>
      ` : ''}

      ${!success ? '<button class="shield-hit-area" type="button" aria-label="长按守护"></button>' : ''}
    `;

    const closeButton = stage.querySelector('.shield-close-button');
    closeButton?.addEventListener('mousedown', closeEffect);
    closeButton?.addEventListener('touchstart', closeEffect, { passive: false });

    const hitArea = stage.querySelector('.shield-hit-area');
    hitArea?.addEventListener('mousedown', startCharge);
    hitArea?.addEventListener('mouseup', stopCharge);
    hitArea?.addEventListener('mouseleave', stopCharge);
    hitArea?.addEventListener('touchstart', startCharge, { passive: false });
    hitArea?.addEventListener('touchend', stopCharge);
    hitArea?.addEventListener('touchcancel', stopCharge);

    if (showLottie) {
      animation?.destroy?.();
      animation = mountLottie(stage.querySelector('.lottie-effect'), asset('guard-demo/videos/bodong.json'), { loop: true, autoplay: true }, manager);
    } else {
      animation?.destroy?.();
      animation = null;
    }
  };

  const addFloatingText = () => {
    if (!isPressing || success) return;
    nextTextId += 1;
    const id = nextTextId;
    const item = {
      id,
      text: FLOATING_WORDS[Math.floor(Math.random() * FLOATING_WORDS.length)],
      x: Math.random() * 60 - 30,
      y: Math.random() * 22 - 8,
      drift: Math.random() * 28 - 14,
    };
    floatingTexts = [...floatingTexts.slice(-6), item];
    const node = document.createElement('span');
    node.className = 'floating-word';
    node.textContent = item.text;
    node.style.setProperty('--float-x', `${item.x}px`);
    node.style.setProperty('--float-y', `${item.y}px`);
    node.style.setProperty('--float-drift', `${item.drift}px`);
    stage.querySelector('.shield-effect')?.insertBefore(node, stage.querySelector('.center-shield'));
    const timer = window.setTimeout(() => {
      floatingTexts = floatingTexts.filter((floatingText) => floatingText.id !== id);
      node.remove();
    }, 1300);
    manager?.addCleanup?.(() => window.clearTimeout(timer));
  };

  const stopFloating = () => {
    window.clearInterval(floatingTimer);
    floatingTimer = 0;
  };

  const updateProgress = () => {
    const elapsed = Date.now() - startedAt;
    progress = Math.min(elapsed / CHARGE_DURATION, 1);

    if (progress >= 1) {
      isPressing = false;
      success = true;
      navigator.vibrate?.(45);
      stopFloating();
      emit(props, { hold_duration_ms: CHARGE_DURATION, guard_value: 100, completed: true }, 'shield_hold');
      renderGuard();
      successTimer = window.setTimeout(() => {
        isFinished = true;
        props.onDismiss('completed');
        renderGuard();
      }, SUCCESS_HOLD);
      return;
    }

    if (!animation && progress > 0) {
      renderGuard();
    } else {
      stage.querySelector('.shield-effect')?.style.setProperty('--progress', String(progress));
    }
    frameId = window.requestAnimationFrame(updateProgress);
  };

  const startCharge = (event) => {
    event.preventDefault();
    if (isFinished || success) return;
    showClose = false;
    navigator.vibrate?.(20);
    startedAt = Date.now();
    progress = 0;
    isVisible = true;
    isExiting = false;
    isPressing = true;
    renderGuard();
    addFloatingText();
    stopFloating();
    floatingTimer = window.setInterval(addFloatingText, 360);
    frameId = window.requestAnimationFrame(updateProgress);
  };

  const stopCharge = () => {
    if (isFinished || success || !isPressing) return;
    isPressing = false;
    isFinished = true;
    stopFloating();
    window.cancelAnimationFrame(frameId);
    emit(props, {
      hold_duration_ms: Math.max(0, Date.now() - startedAt),
      guard_value: Math.round(progress * 100),
      completed: false,
    }, 'shield_hold');
    props.onDismiss('closed');
    renderGuard();
  };

  const closeEffect = (event) => {
    event.preventDefault();
    event.stopPropagation();
    isPressing = false;
    isFinished = true;
    stopFloating();
    window.cancelAnimationFrame(frameId);
    props.onDismiss('closed');
    renderGuard();
  };

  manager?.addCleanup?.(() => {
    window.cancelAnimationFrame(frameId);
    window.clearTimeout(successTimer);
    stopFloating();
    animation?.destroy?.();
  });

  renderGuard();
}

function TeamCheer(container, props, manager) {
  const stage = createOriginalStage(container, asset('zhandui-demo/src/components/FactionCheerOverlay/styles.css'), [effectLiftCss()]);
  const shadowRoot = stage.getRootNode();
  const styleLink = [...shadowRoot.querySelectorAll('link[rel="stylesheet"]')]
    .find((link) => link.href.includes('zhandui-demo/src/components/FactionCheerOverlay/styles.css'));
  let revealTimer = 0;
  let revealed = false;
  const revealStage = () => {
    if (revealed) return;
    revealed = true;
    window.clearTimeout(revealTimer);
    window.requestAnimationFrame(() => {
      stage.style.visibility = 'visible';
    });
  };
  stage.style.visibility = 'hidden';
  if (styleLink?.sheet) {
    revealStage();
  } else {
    styleLink?.addEventListener('load', revealStage, { once: true });
    revealTimer = window.setTimeout(revealStage, 1200);
  }
  manager?.addCleanup?.(() => {
    window.clearTimeout(revealTimer);
    styleLink?.removeEventListener('load', revealStage);
  });
  const configOptions = props.interactionPoint.config?.team_options || [];
  const left = {
    id: configOptions[0]?.team_key || 'red',
    name: configOptions[0]?.label || '红方阵营',
    color: configOptions[0]?.color || '#ff3b35',
    score: Number(configOptions[0]?.score ?? 126380),
  };
  const right = {
    id: configOptions[1]?.team_key || 'blue',
    name: configOptions[1]?.label || '蓝方阵营',
    color: configOptions[1]?.color || '#2f80ff',
    score: Number(configOptions[1]?.score ?? 117240),
  };
  let selectedFactionId = props.interactionPoint.config?.selected_team || 'blue';
  let cheerCount = Number(props.interactionPoint.config?.cheer_count ?? 27);
  let contribution = Number(props.interactionPoint.config?.contribution ?? 27);
  let pointerStartX = null;

  const formatScore = (score) => score.toLocaleString('en-US');
  const updatePercents = () => {
    const total = left.score + right.score || 1;
    left.percent = Math.round((left.score / total) * 100);
    right.percent = 100 - left.percent;
  };
  const selectedFaction = () => {
    if (selectedFactionId === left.id) return left;
    if (selectedFactionId === right.id) return right;
    return null;
  };
  const stripFactionSuffix = (name) => name.replace('阵营', '').replace('闃佃惀', '');
  const icon = (type) => {
    if (type === 'left') {
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m11 17-5-5 5-5v10Zm7 0-5-5 5-5v10Z" fill="currentColor"/></svg>';
    }
    if (type === 'right') {
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m13 7 5 5-5 5V7ZM6 7l5 5-5 5V7Z" fill="currentColor"/></svg>';
    }
    if (type === 'record') {
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19V9h3v10H5Zm5 0V5h4v14h-4Zm6 0v-7h3v7h-3Z" fill="currentColor"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2 5 13h5l-1 9 8-12h-5l1-8Z" fill="currentColor"/></svg>';
  };
  const waveMarkup = (side) => {
    const redMain = 'M0 46 C8 49 22 38 32 46 C42 56 52 25 64 44 C74 64 86 73 96 43 C106 12 118 1 128 45 C139 78 149 66 160 47 C171 26 181 19 192 48 C203 69 213 42 224 31 C235 16 245 5 256 47 C267 78 278 58 288 44 C299 27 309 43 320 46';
    const blueMain = 'M0 46 C8 41 22 52 32 46 C43 40 54 34 64 45 C75 57 86 61 96 46 C107 30 118 19 128 45 C139 70 149 55 160 46 C171 36 181 39 192 47 C203 56 214 47 224 35 C235 24 245 26 256 48 C267 69 278 49 288 45 C299 40 309 47 320 45';
    const alt = side === 'left'
      ? 'M0 50 C8 39 22 57 32 43 C43 29 54 49 64 58 C75 70 86 44 96 29 C107 10 118 -2 128 47 C139 82 149 62 160 40 C171 16 181 37 192 54 C203 73 214 31 224 18 C235 7 245 36 256 57 C267 80 278 45 288 35 C299 24 309 53 320 41'
      : 'M0 49 C8 54 22 38 32 46 C43 54 54 47 64 39 C75 30 86 58 96 47 C107 35 118 13 128 45 C139 73 149 51 160 42 C171 33 181 58 192 49 C203 40 214 62 224 46 C235 29 245 17 256 49 C267 70 278 53 288 48 C299 44 309 51 320 48';
    const base = side === 'left' ? redMain : blueMain;
    const fill = `${base} L320 80 L0 80 Z`;
    const fillAlt = `${alt} L320 80 L0 80 Z`;
    const duration = side === 'left' ? '38s' : '44s';
    return `
      <div class="fco-waveform" aria-hidden="true">
        <svg viewBox="0 0 320 80" preserveAspectRatio="none" focusable="false">
          <path class="fco-wave-glow" d="${base}">
            <animate attributeName="d" dur="${duration}" repeatCount="indefinite" values="${base}; ${alt}; ${base}" />
          </path>
          <path class="fco-wave-main" d="${base}">
            <animate attributeName="d" dur="${duration}" repeatCount="indefinite" values="${base}; ${alt}; ${base}" />
          </path>
          <path class="fco-wave-secondary" d="${alt}">
            <animate attributeName="d" dur="${side === 'left' ? '52s' : '58s'}" repeatCount="indefinite" values="${alt}; ${base}; ${alt}" />
          </path>
          <path class="fco-wave-fill" d="${fill}">
            <animate attributeName="d" dur="${duration}" repeatCount="indefinite" values="${fill}; ${fillAlt}; ${fill}" />
          </path>
          <g class="fco-wave-sparks">
            <circle cx="84" cy="46" r="1.8" />
            <circle cx="108" cy="46" r="2.2" />
            <circle cx="216" cy="45" r="2" />
            <circle cx="274" cy="45" r="1.5" />
          </g>
        </svg>
        <span class="fco-wave-ticks"></span>
      </div>
    `;
  };
  const factionSideMarkup = (faction, side) => {
    const directionText = side === 'left' ? '向左滑动选红方' : '向右滑动选蓝方';
    return `
      <button
        class="fco-faction-side fco-faction-side-${side}"
        data-team="${faction.id}"
        type="button"
        style="--faction-color:${faction.color}"
        aria-pressed="${selectedFactionId === faction.id}"
        aria-label="${directionText}，${faction.name}，当前 ${faction.score}"
      >
        <div class="fco-faction-name">
          ${side === 'left' ? icon('flame') : ''}
          <span>${faction.name}</span>
          ${side === 'right' ? icon('flame') : ''}
        </div>
        <strong class="fco-faction-score">${formatScore(faction.score)}</strong>
        <span class="fco-faction-percent">${faction.percent}%</span>
        ${waveMarkup(side)}
        <div class="fco-swipe-hint">
          ${side === 'left' ? icon('left') : ''}
          <span>${directionText}</span>
          ${side === 'right' ? icon('right') : ''}
        </div>
      </button>
    `;
  };
  const renderSummary = () => {
    const faction = selectedFaction();
    if (!faction) return '';
    const shortName = stripFactionSuffix(faction.name);
    return `
      <p class="fco-result-summary" style="--selected-color:${faction.color}">
        <span class="fco-result-full">
          你为${shortName}助威 <strong>${cheerCount}</strong> 次，贡献 <strong>${contribution}</strong> 点支持
        </span>
        <span class="fco-result-short">
          ${shortName}助威 <strong>${cheerCount}</strong> 次 · 贡献 <strong>${contribution}</strong> 点
        </span>
      </p>
    `;
  };
  const selectFaction = (id) => {
    selectedFactionId = id;
  };
  const cheerForFaction = (id, eventType = 'team_choose') => {
    selectFaction(id);
    cheerCount += 1;
    contribution += 1;
    if (id === left.id) {
      left.score += 1;
    } else {
      right.score += 1;
    }
    renderTeam();
    emit(props, {
      chosen_team: id,
      cheer_count: cheerCount,
      contribution,
      left_score: left.score,
      right_score: right.score,
    }, eventType);
  };
  const onPointerDown = (event) => {
    pointerStartX = event.clientX;
  };
  const onPointerUp = (event) => {
    if (pointerStartX === null) return;
    const deltaX = event.clientX - pointerStartX;
    pointerStartX = null;
    if (Math.abs(deltaX) < 44) return;
    cheerForFaction(deltaX < 0 ? left.id : right.id, 'team_cheer');
  };
  const openRecord = (event) => {
    event.stopPropagation();
    emit(props, {
      selected_team: selectedFactionId,
      cheer_count: cheerCount,
      contribution,
    }, 'team_record_open');
  };
  function renderTeam() {
    updatePercents();
    const selected = selectedFaction();
    stage.innerHTML = `
      <style>
        .fco-overlay {
          bottom: 0 !important;
          --fco-shape: polygon(
            4% 28%,
            5.5% 17%,
            10% 9%,
            17% 6.5%,
            30% 7.2%,
            42% 7%,
            52% 7.3%,
            64% 7%,
            78% 6.8%,
            88% 8.8%,
            94% 17%,
            97% 31%,
            98% 50%,
            96% 69%,
            91.5% 83%,
            82% 91%,
            68% 96%,
            52% 97.2%,
            35% 96.8%,
            22% 93.5%,
            12% 86.5%,
            5.5% 74%,
            3% 56%,
            3% 41%
          );
        }
        .fco-glass-layer,
        .fco-atmosphere {
          -webkit-clip-path: var(--fco-shape) !important;
          clip-path: var(--fco-shape) !important;
          border-radius: 0 !important;
        }
        .fco-glass-layer::after {
          -webkit-clip-path: var(--fco-shape) !important;
          clip-path: var(--fco-shape) !important;
        }
        .fco-waveform svg {
          animation: zhanduiWaveDrift 3.4s ease-in-out infinite alternate !important;
        }
        .fco-wave-main {
          stroke-dasharray: 18 10 !important;
          animation-duration: 3.2s !important;
        }
        .fco-wave-secondary {
          animation-duration: 4.1s !important;
        }
        .fco-wave-ticks {
          animation: zhanduiTickDrift 2.6s linear infinite !important;
          background-position: 0 0, 0 0;
        }
        @keyframes zhanduiWaveDrift {
          0% { transform: translateX(-4px) scaleY(0.92); }
          50% { transform: translateX(3px) scaleY(1.08); }
          100% { transform: translateX(6px) scaleY(0.96); }
        }
        @keyframes zhanduiTickDrift {
          from { background-position: 0 0, 0 0; }
          to { background-position: 36px 0, 0 0; }
        }
        .fco-faction-side-right .fco-waveform svg,
        .fco-faction-side-right .fco-wave-ticks {
          transform: scaleX(-1);
        }
        .fco-faction-side-right .fco-waveform svg {
          animation-name: zhanduiWaveDriftRight !important;
        }
        @keyframes zhanduiWaveDriftRight {
          0% { transform: scaleX(-1) translateX(-4px) scaleY(0.92); }
          50% { transform: scaleX(-1) translateX(3px) scaleY(1.08); }
          100% { transform: scaleX(-1) translateX(6px) scaleY(0.96); }
        }
      </style>
      <section
        class="fco-overlay fco-state-cheering"
        style="--left-color:${left.color};--right-color:${right.color};--selected-color:${selected?.color || right.color}"
        role="group"
        aria-label="阵营助威互动浮层"
      >
        <div class="fco-glass-layer" aria-hidden="true"></div>
        <div class="fco-atmosphere" aria-hidden="true">
          <span class="fco-particles fco-particles-left"></span>
          <span class="fco-particles fco-particles-right"></span>
          <span class="fco-particles fco-particles-center"></span>
          <span class="fco-energy fco-energy-left"></span>
          <span class="fco-energy fco-energy-right"></span>
        </div>
        <svg class="fco-organic-outline" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="fco-outline-gradient" x1="0%" y1="38%" x2="100%" y2="62%">
              <stop offset="0%" stop-color="${left.color}" stop-opacity="0.34"></stop>
              <stop offset="46%" stop-color="#9f7cff" stop-opacity="0.2"></stop>
              <stop offset="100%" stop-color="${right.color}" stop-opacity="0.34"></stop>
            </linearGradient>
            <linearGradient id="fco-outline-glow-gradient" x1="0%" y1="38%" x2="100%" y2="62%">
              <stop offset="0%" stop-color="${left.color}" stop-opacity="0.2"></stop>
              <stop offset="50%" stop-color="#8fb4ff" stop-opacity="0.16"></stop>
              <stop offset="100%" stop-color="${right.color}" stop-opacity="0.22"></stop>
            </linearGradient>
            <clipPath id="fco-hud-shape" clipPathUnits="objectBoundingBox">
              <path d="M.018 .39C.012 .18 .112 .035 .292 .055C.382 .065 .43 .035 .512 .04C.604 .045 .665 .112 .752 .09C.888 .056 .97 .162 .978 .352C.986 .548 .948 .814 .822 .898C.716 .967 .616 .923 .508 .953C.391 .986 .284 .958 .176 .902C.078 .851 .026 .714 .018 .548C.015 .486 .016 .433 .018 .39Z"></path>
            </clipPath>
          </defs>
          <path class="fco-outline-glow" d="M.018 .39C.012 .18 .112 .035 .292 .055C.382 .065 .43 .035 .512 .04C.604 .045 .665 .112 .752 .09C.888 .056 .97 .162 .978 .352C.986 .548 .948 .814 .822 .898C.716 .967 .616 .923 .508 .953C.391 .986 .284 .958 .176 .902C.078 .851 .026 .714 .018 .548C.015 .486 .016 .433 .018 .39Z"></path>
          <path class="fco-outline-line" d="M.018 .39C.012 .18 .112 .035 .292 .055C.382 .065 .43 .035 .512 .04C.604 .045 .665 .112 .752 .09C.888 .056 .97 .162 .978 .352C.986 .548 .948 .814 .822 .898C.716 .967 .616 .923 .508 .953C.391 .986 .284 .958 .176 .902C.078 .851 .026 .714 .018 .548C.015 .486 .016 .433 .018 .39Z"></path>
        </svg>
        <div class="fco-top-area">
          <div class="fco-timer" aria-label="助威倒计时 00:05:27">
            <span>助威倒计时</span>
            <strong>${props.interactionPoint.config?.timer_text || '00:05:27'}</strong>
          </div>
          <div class="fco-character-stage fco-character-stage-composite">
            <img src="${asset('zhandui-demo/assets/duel-characters.png')}" alt="" draggable="false" />
          </div>
        </div>
        <div class="fco-prompt" aria-label="选择阵营，为TA助威">
          <span class="fco-prompt-line"></span>
          ${icon('right')}
          <strong>${props.interactionPoint.config?.prompt_text || '选择阵营，为TA助威'}</strong>
          ${icon('left')}
          <span class="fco-prompt-line"></span>
        </div>
        <div class="fco-vote-panel">
          ${factionSideMarkup(left, 'left')}
          ${factionSideMarkup(right, 'right')}
          <div class="fco-vs-badge" aria-hidden="true"><span>VS</span></div>
        </div>
        <footer class="fco-footer">
          ${renderSummary()}
          <button class="fco-record-button" type="button">
            ${icon('record')}
            <span>助威记录</span>
          </button>
        </footer>
      </section>
    `;
    const overlay = stage.querySelector('.fco-overlay');
    overlay?.addEventListener('pointerdown', onPointerDown);
    overlay?.addEventListener('pointerup', onPointerUp);
    overlay?.addEventListener('pointercancel', () => {
      pointerStartX = null;
    });
    stage.querySelectorAll('[data-team]').forEach((button) => {
      button.addEventListener('click', () => cheerForFaction(button.dataset.team, selectedFactionId ? 'team_cheer' : 'team_choose'));
    });
    stage.querySelector('.fco-record-button')?.addEventListener('click', openRecord);
  }

  renderTeam();
}

function PredictionCard(container, props, manager) {
  return realOptionCard(container, props, {
    className: 'real-prediction',
    title: '剧情预测卡',
    cssPath: asset('yuce-demo/src/styles/app.css'),
    card: asset('yuce-demo/images/card.png'),
    eventType: 'prediction_submit',
    question: props.interactionPoint.config?.question || 'TA 会说出真相吗？',
  }, manager);
}

function ClueJudgeCard(container, props, manager) {
  return realOptionCard(container, props, {
    className: 'real-clue',
    title: '线索判断卡',
    cssPath: asset('xiansuo-demo/src/styles/app.css'),
    card: asset('xiansuo-demo/images/card.png'),
    eventType: 'clue_judge',
    question: props.interactionPoint.config?.question || '这是重要线索吗？',
  }, manager);
}

function EpisodeEndPrediction(container, props, manager) {
  return realOptionCard(container, props, {
    className: 'real-end-prediction',
    title: '剧尾预测卡',
    cssPath: asset('yuce-end-demo/src/styles/app.css'),
    card: asset('yuce-end-demo/images/card.png'),
    eventType: 'prediction_submit',
    question: props.interactionPoint.config?.question || '下一集会怎样？',
  }, manager);
}

function UnknownInteraction(container, props, manager) {
  const body = createStage(container, props, manager, 'real-unknown', props.interactionPoint.component, '未知组件，已使用兜底交互');
  body.innerHTML = `<button class="fallback-button" type="button">记录互动</button>`;
  body.querySelector('button').addEventListener('click', () => emit(props, { fallback: true }));
}

function EmotionBuffer(container, props, manager) {
  const stage = createOriginalStage(container, asset('huanchong-demo/src/styles/app.css'), [effectLiftCss()]);
  let countdown = 5;
  let isExiting = false;
  let isVisible = true;
  let isHolding = false;
  let countdownTimer = 0;
  let hideTimer = 0;
  let skipTimer = 0;
  let holdStartedAt = 0;
  let hasInteracted = false;
  let hasSkipped = false;

  const cleanup = () => {
    window.clearTimeout(countdownTimer);
    window.clearTimeout(hideTimer);
    window.clearTimeout(skipTimer);
  };
  manager?.addCleanup?.(cleanup);

  const scheduleCountdown = () => {
    window.clearTimeout(countdownTimer);
    if (!isVisible) return;
    if (countdown > 1) {
      countdownTimer = window.setTimeout(() => {
        countdown -= 1;
        scheduleCountdown();
      }, 1000);
      return;
    }
    countdownTimer = window.setTimeout(() => {
      isExiting = true;
      countdown = 0;
      renderBuffer();
      hideTimer = window.setTimeout(() => {
        isVisible = false;
        renderBuffer();
        props.onDismiss('timeout');
      }, 560);
    }, 1000);
  };

  const startHold = (event) => {
    event.preventDefault();
    if (isHolding) return;
    isHolding = true;
    hasSkipped = false;
    holdStartedAt = performance.now();
    window.clearTimeout(skipTimer);
    skipTimer = window.setTimeout(() => {
      if (!isHolding || hasSkipped) return;
      hasSkipped = true;
      emit(props, {
        hold_duration_ms: 2000,
        buffer_reason: props.interactionPoint.highlight_reason,
        completed: true,
        skip_forward_seconds: 10,
      }, 'emotion_buffer_enter');
    }, 2000);
    renderBuffer();
    if (!hasInteracted) {
      hasInteracted = true;
      emit(props, {
        buffer_reason: props.interactionPoint.highlight_reason,
        action: 'pointer_down',
      }, 'emotion_buffer_enter');
    }
  };

  const stopHold = () => {
    if (!isHolding) return;
    const duration = Math.round(performance.now() - holdStartedAt);
    isHolding = false;
    window.clearTimeout(skipTimer);
    renderBuffer();
    emit(props, {
      hold_duration_ms: duration,
      buffer_reason: props.interactionPoint.highlight_reason,
      completed: duration >= 1500,
    }, 'emotion_buffer_enter');
  };

  function renderBuffer() {
    if (!isVisible) {
      stage.innerHTML = '';
      return;
    }

    stage.innerHTML = `
      <section class="phone-frame" aria-label="Drama buffer demo">
        <div class="predict-zone ${isExiting ? 'is-fading-out' : ''}">
          <article class="predict-card">
            <div class="drama-card-media">
              <img
                class="drama-effect drama-effect--card1"
                src="${asset('huanchong-demo/images/card1-effect.png')}"
                alt=""
                aria-hidden="true"
                draggable="false"
              />
              <div class="buffer-button-wrap ${isHolding ? 'holding' : ''}">
                <span class="energy-ring ring-one" aria-hidden="true"></span>
                <span class="energy-ring ring-two" aria-hidden="true"></span>
                <span class="energy-ring ring-three" aria-hidden="true"></span>
                <button
                  class="drama-effect-button drama-effect-button--card2"
                  type="button"
                  aria-label="Trigger buffer effect"
                >
                  <img
                    class="drama-effect drama-effect--card2"
                    src="${asset('huanchong-demo/images/card2-effect.png')}"
                    alt=""
                    aria-hidden="true"
                    draggable="false"
                  />
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    `;

    const button = stage.querySelector('.drama-effect-button--card2');
    button?.addEventListener('pointerdown', startHold);
    button?.addEventListener('pointerup', stopHold);
    button?.addEventListener('pointerleave', stopHold);
    button?.addEventListener('pointercancel', stopHold);
  }

  renderBuffer();
  scheduleCountdown();
  return cleanup;
}

function realOptionCard(container, props, options, manager) {
  const config = props.interactionPoint.config || {};
  const choices = config.options || [
    { option_key: 'yes', label: '会' },
    { option_key: 'no', label: '不会' },
  ];
  const stage = createOriginalStage(container, options.cssPath, [effectLiftCss()]);
  let hoveredOption = '';
  let selectedOption = '';
  let isCardExiting = false;
  let isCardVisible = true;
  let countdown = 4;
  let countdownTimer = 0;
  let exitTimer = 0;
  let hideTimer = 0;

  const clearTimers = () => {
    window.clearTimeout(countdownTimer);
    window.clearTimeout(exitTimer);
    window.clearTimeout(hideTimer);
  };
  const cleanup = () => clearTimers();
  manager?.addCleanup?.(cleanup);

  const dismissCard = (delay = 0, reason = 'timeout') => {
    window.clearTimeout(exitTimer);
    window.clearTimeout(hideTimer);
    exitTimer = window.setTimeout(() => {
      isCardExiting = true;
      renderCard();
    }, delay);
    hideTimer = window.setTimeout(() => {
      isCardVisible = false;
      renderCard();
      props.onDismiss(reason);
    }, delay + 560);
  };

  const startCountdown = () => {
    window.clearTimeout(countdownTimer);
    if (!isCardVisible || isCardExiting) return;
    countdownTimer = window.setTimeout(() => {
      if (countdown > 1) {
        countdown -= 1;
        renderCard();
        startCountdown();
        return;
      }
      dismissCard(0, 'timeout');
    }, 1000);
  };

  const setActiveOption = (optionId) => {
    hoveredOption = optionId;
    const media = stage.querySelector('.drama-card-media');
    if (!media) return;
    const activeOption = hoveredOption || selectedOption;
    media.className = `drama-card-media ${activeOption ? `is-${activeOption}` : ''}`;
  };

  const selectOption = (button) => {
    if (selectedOption || isCardExiting) return;
    selectedOption = button.dataset.option;
    hoveredOption = '';
    stage.querySelectorAll('[data-option]').forEach((item) => {
      item.classList.toggle('is-selected', item === button);
      item.setAttribute('aria-pressed', String(item === button));
    });
    setActiveOption(selectedOption);
    const tip = stage.querySelector('.recorded-tip');
    if (tip) tip.textContent = '已记录你的预测，后续剧情验证';
    emit(props, {
      prediction_id: config.prediction_id,
      clue_id: config.clue_id,
      choice: button.dataset.choice,
      judgment: button.dataset.choice,
      reveal_episode_id: config.reveal_episode_id,
    }, options.eventType);
    dismissCard(500, 'selected');
  };

  function renderCard() {
    if (!isCardVisible) {
      stage.innerHTML = '';
      return;
    }

    const activeOption = hoveredOption || selectedOption;
    stage.innerHTML = `
      <style>
        .prediction-card-adjust .predict-zone {
          transform: translateY(12px) scale(0.6667) !important;
        }
        .prediction-card-adjust .predict-zone.is-fading-out {
          transform: translateY(30px) scale(0.6667) !important;
        }
      </style>
      <section class="phone-frame prediction-card-adjust" aria-label="剧情预测特效">
        <div class="countdown-copy countdown-copy--effect ${isCardExiting ? 'is-fading-out' : ''}">
          <span>精彩还未结束...</span>
          <strong>${countdown}s</strong>
        </div>
        <div class="predict-zone ${isCardExiting ? 'is-fading-out' : ''}">
          <article class="predict-card">
            <div class="drama-card-media ${activeOption ? `is-${activeOption}` : ''}">
              <img class="drama-card-img" src="${options.card}" alt="剧情预测卡" draggable="false" />
              <div class="drama-card-dim" aria-hidden="true"></div>
              <div class="drama-card-glow drama-card-glow--yes" style="background-image:url('${options.card}')" aria-hidden="true"></div>
              <div class="drama-card-glow drama-card-glow--no" style="background-image:url('${options.card}')" aria-hidden="true"></div>
              <div class="option-overlay" role="group" aria-label="选择剧情预测">
                <button
                  class="option-hotspot option-hotspot--yes ${selectedOption === 'yes' ? 'is-selected' : ''}"
                  data-option="yes"
                  data-choice="${choices[0]?.option_key || 'yes'}"
                  type="button"
                  aria-label="${choices[0]?.label || '会'}"
                  aria-pressed="${selectedOption === 'yes'}"
                ></button>
                <button
                  class="option-hotspot option-hotspot--no ${selectedOption === 'no' ? 'is-selected' : ''}"
                  data-option="no"
                  data-choice="${choices[1]?.option_key || 'no'}"
                  type="button"
                  aria-label="${choices[1]?.label || '不会'}"
                  aria-pressed="${selectedOption === 'no'}"
                ></button>
              </div>
            </div>
            ${selectedOption ? '<p class="recorded-tip recorded-tip--image" role="status">已记录你的预测，后续剧情验证</p>' : ''}
          </article>
        </div>
      </section>
    `;
    stage.querySelectorAll('[data-option]').forEach((button) => {
      const optionId = button.dataset.option;
      button.addEventListener('mouseenter', () => setActiveOption(optionId));
      button.addEventListener('mouseleave', () => setActiveOption(''));
      button.addEventListener('focus', () => setActiveOption(optionId));
      button.addEventListener('blur', () => setActiveOption(''));
      button.addEventListener('click', () => selectOption(button));
    });
  }

  renderCard();
  startCountdown();
  return cleanup;
}

function getLocalPoint(node, event) {
  const rect = node.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
}

export const registry = {
  celebrate_confetti: CelebrateConfetti,
  anger_release: AngerRelease,
  tear_resonance: TearResonance,
  laugh_burst: LaughBurst,
  shatter_strike: ShatterStrike,
  sugar_storm: SugarStorm,
  guardian_shield: GuardianShield,
  team_cheer: TeamCheer,
  prediction_card: PredictionCard,
  clue_judge_card: ClueJudgeCard,
  episode_end_prediction: EpisodeEndPrediction,
  emotion_buffer: EmotionBuffer,
};
