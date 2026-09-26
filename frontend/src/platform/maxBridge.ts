export type MaxPlatform = 'ios' | 'android' | 'desktop' | 'web' | string;

export interface MaxBackButton {
  isVisible?: boolean;
  show: () => void;
  hide: () => void;
  onClick: (callback: () => void) => void;
  offClick: (callback: () => void) => void;
}

export interface MaxWebApp {
  initData?: string;
  initDataUnsafe?: {
    start_param?: string;
    user?: { first_name?: string; last_name?: string; photo_url?: string };
  };
  platform?: MaxPlatform;
  version?: string;
  deviceName?: string;
  BackButton?: MaxBackButton;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  HapticFeedback?: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
  };
  ScreenCapture?: {
    disableScreenCapture: () => Promise<unknown>;
    enableScreenCapture: () => Promise<unknown>;
  };
  shareMaxContent?: (params: { text?: string; link?: string }) => void;
  openCodeReader?: (callback?: (value: string) => void) => void;
  requestScreenMaxBrightness?: () => Promise<unknown>;
  restoreScreenBrightness?: () => Promise<unknown>;
  getViewportSize?: () => Promise<{ height: string; width: string }>;
}

declare global {
  interface Window {
    WebApp?: MaxWebApp;
  }
}

export function getMaxWebApp(): MaxWebApp | undefined {
  return typeof window === 'undefined' ? undefined : window.WebApp;
}

export function isMaxRuntime(): boolean {
  return Boolean(getMaxWebApp()?.initData);
}

export function getInitData(): string {
  return getMaxWebApp()?.initData ?? '';
}

export function getStartParam(): string {
  return getMaxWebApp()?.initDataUnsafe?.start_param ?? '';
}

export function getDisplayNameHint(): string | undefined {
  const user = getMaxWebApp()?.initDataUnsafe?.user;
  return [user?.first_name, user?.last_name].filter(Boolean).join(' ') || undefined;
}

export function setClosingConfirmation(enabled: boolean): void {
  const webApp = getMaxWebApp();
  if (enabled) webApp?.enableClosingConfirmation?.();
  else webApp?.disableClosingConfirmation?.();
}

export function showBackButton(onBack: () => void): () => void {
  const backButton = getMaxWebApp()?.BackButton;
  if (!backButton) return () => undefined;

  backButton.show();
  backButton.onClick(onBack);
  return () => {
    backButton.offClick(onBack);
    backButton.hide();
  };
}

export function hapticLight(): void {
  getMaxWebApp()?.HapticFeedback?.impactOccurred('light');
}

export function setScreenCaptureProtection(enabled: boolean): void {
  const screenCapture = getMaxWebApp()?.ScreenCapture;
  const operation = enabled ? screenCapture?.disableScreenCapture : screenCapture?.enableScreenCapture;
  void operation?.().catch(() => {
    // This capability is optional in browser fallback and older MAX clients.
  });
}

export async function shareMaxContent(content: { text: string; link: string }): Promise<void> {
  const share = getMaxWebApp()?.shareMaxContent;
  if (share) {
    share(content);
    return;
  }
  if (navigator.share) {
    await navigator.share({ text: content.text, url: content.link });
    return;
  }
  await navigator.clipboard?.writeText(`${content.text}\n${content.link}`);
}

export function openCodeReader(): Promise<string | null> {
  const reader = getMaxWebApp()?.openCodeReader;
  if (!reader) return Promise.resolve(null);
  return new Promise((resolve) => reader((value) => resolve(value || null)));
}

export function setQrBrightness(enabled: boolean): void {
  const app = getMaxWebApp();
  const operation = enabled ? app?.requestScreenMaxBrightness : app?.restoreScreenBrightness;
  void operation?.().catch(() => undefined);
}
