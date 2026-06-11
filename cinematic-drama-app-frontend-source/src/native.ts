import { App as CapacitorApp } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import { StatusBar, Style } from '@capacitor/status-bar';

const APP_BACKGROUND = '#0a0a0b';

export function initNativeShell() {
  if (!Capacitor.isNativePlatform()) return;

  StatusBar.setStyle({ style: Style.Dark }).catch(() => undefined);
  StatusBar.setBackgroundColor({ color: APP_BACKGROUND }).catch(() => undefined);

  if (Capacitor.getPlatform() !== 'android') return;

  CapacitorApp.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack || window.history.length > 1) {
      window.history.back();
      return;
    }
    CapacitorApp.exitApp().catch(() => undefined);
  }).catch(() => undefined);
}
