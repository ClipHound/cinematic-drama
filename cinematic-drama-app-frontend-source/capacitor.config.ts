import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.demo.cinematicdrama',
  appName: 'Cinematic Drama',
  webDir: 'dist',
  server: {
    androidScheme: 'http',
  },
};

export default config;
