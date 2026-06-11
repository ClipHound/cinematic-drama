import { apiUrl } from '../data/catalog';
import { getDeviceId } from '../data/device';

type EventRecord = {
  id: string;
  dramaId: string;
  episodeNumber: number;
  pointId: string;
  type: string;
  actionData: Record<string, unknown>;
  atMs: number;
  createdAt: string;
};

const STORAGE_KEY = 'cinematic-drama-events';

export class LocalEventQueue {
  private events: EventRecord[] = [];

  constructor(private onStatus?: (text: string) => void) {
    this.events = this.restore();
  }

  enqueue(event: Omit<EventRecord, 'id' | 'createdAt'>) {
    const record: EventRecord = {
      ...event,
      id: crypto.randomUUID?.() || `event-${Date.now()}`,
      createdAt: new Date().toISOString(),
    };
    this.events.push(record);
    this.persist();
    this.onStatus?.(`已记录 ${this.events.length} 条互动事件`);
  }

  async flush() {
    const count = this.events.length;
    if (!count) {
      this.onStatus?.('暂无待上报事件');
      return;
    }

    const pending = [...this.events];
    const response = await fetch(apiUrl('/api/interactions'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Device-Id': getDeviceId(),
      },
      body: JSON.stringify({ events: pending }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null) as { message?: string } | null;
      throw new Error(payload?.message || '互动事件上报失败');
    }

    const sent = new Set(pending.map((event) => event.id));
    this.events = this.events.filter((event) => !sent.has(event.id));
    this.persist();
    this.onStatus?.(`已上报 ${count} 条互动事件`);
  }

  private persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.events));
  }

  private restore(): EventRecord[] {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as EventRecord[];
    } catch {
      return [];
    }
  }
}
