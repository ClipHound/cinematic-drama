export class InteractionTimeline {
  constructor({ manifest, onActivate, onDismiss, onTick }) {
    this.manifest = manifest;
    this.onActivate = onActivate;
    this.onDismiss = onDismiss;
    this.onTick = onTick;
    this.startedAt = 0;
    this.offsetMs = 0;
    this.currentMs = 0;
    this.activePoint = null;
    this.completed = new Set();
    this.running = false;
    this.rafId = null;
  }

  play(externalClock = false) {
    if (this.running) return;
    this.running = true;
    this.startedAt = performance.now() - this.offsetMs;
    if (externalClock) return;
    this.loop();
  }

  pause() {
    if (!this.running) return;
    this.running = false;
    this.offsetMs = this.currentMs;
    cancelAnimationFrame(this.rafId);
  }

  seek(ms) {
    this.offsetMs = this.clampMs(ms);
    this.currentMs = this.offsetMs;
    this.startedAt = performance.now() - this.offsetMs;
    if (this.activePoint && !this.isPointActiveAt(this.activePoint, this.currentMs)) {
      this.dismissActive('skip');
    }
    this.rearmCompletedPoints(this.currentMs);
    this.onTick?.(this.currentMs);
  }

  sync(ms) {
    const previousMs = this.currentMs;
    this.currentMs = this.clampMs(ms);
    this.offsetMs = this.currentMs;
    if (this.activePoint && !this.isPointActiveAt(this.activePoint, this.currentMs)) {
      this.dismissActive(this.currentMs > this.activePoint.end_ms ? 'timeout' : 'skip');
    }
    if (this.currentMs < previousMs - 750) {
      this.rearmCompletedPoints(this.currentMs);
    }
    this.matchCurrentPoint();
    this.onTick?.(this.currentMs);
  }

  loop() {
    if (!this.running) return;
    this.currentMs = Math.min(performance.now() - this.startedAt, this.manifest.duration_ms);
    this.matchCurrentPoint();
    this.onTick?.(this.currentMs);
    if (this.currentMs >= this.manifest.duration_ms) {
      this.pause();
      return;
    }
    this.rafId = requestAnimationFrame(() => this.loop());
  }

  matchCurrentPoint() {
    if (this.activePoint && this.currentMs > this.activePoint.end_ms) {
      this.dismissActive('timeout');
    }

    const candidates = this.manifest.interaction_points
      .filter((point) => !this.completed.has(point.id))
      .filter((point) => this.currentMs >= point.start_ms && this.currentMs <= point.end_ms)
      .sort((a, b) => b.priority - a.priority);

    const nextPoint = candidates[0];
    if (!nextPoint) return;

    if (!this.activePoint) {
      this.activate(nextPoint);
      return;
    }

    if (nextPoint.id !== this.activePoint.id && nextPoint.priority >= this.activePoint.priority + 0.2) {
      this.dismissActive('preempted');
      this.activate(nextPoint);
    }
  }

  activate(point) {
    this.activePoint = point;
    this.onActivate?.(point);
  }

  dismissActive(reason) {
    if (!this.activePoint) return;
    const point = this.activePoint;
    this.completed.add(point.id);
    this.activePoint = null;
    this.onDismiss?.(point, reason);
  }

  clampMs(ms) {
    const durationMs = Number.isFinite(this.manifest.duration_ms) ? this.manifest.duration_ms : 0;
    return Math.max(0, Math.min(ms, durationMs));
  }

  isPointActiveAt(point, ms) {
    return ms >= point.start_ms && ms <= point.end_ms;
  }

  rearmCompletedPoints(ms) {
    this.manifest.interaction_points.forEach((point) => {
      if (ms <= point.end_ms) {
        this.completed.delete(point.id);
      }
    });
  }
}
