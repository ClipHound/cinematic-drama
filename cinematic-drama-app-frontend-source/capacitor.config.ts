import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.demo.cinematicdrama',
  appName: 'Cinematic Drama',
  webDir: 'dist',
  server: {
    androidScheme: 'http',
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0a0a0b',
      overlaysWebView: false,
    },
  },
};

export default config;
