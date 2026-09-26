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
  /** Opens the MAX QR reader. Keep this as a method on WebApp: the bridge uses `this`. */
  openCodeReader?: (fileSelect?: boolean) => Promise<string | { value?: unknown } | null | undefined>;
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
  if (!screenCapture) return;
  try {
    // Call bridge methods on their object: detached from it they lose `this` and throw.
    const result = enabled ? screenCapture.disableScreenCapture?.() : screenCapture.enableScreenCapture?.();
    void result?.catch(() => undefined);
  } catch {
    // This capability is optional in browser fallback and older MAX clients.
  }
}

export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Some desktop browsers expose Clipboard API but reject it in an embedded
      // webview. Continue with the user-gesture-compatible fallback below.
    }
  }
  const input = document.createElement('textarea');
  input.value = text;
  input.setAttribute('readonly', '');
  input.style.position = 'fixed';
  input.style.opacity = '0';
  document.body.append(input);
  input.select();
  const copied = document.execCommand('copy');
  input.remove();
  if (!copied) throw new Error('Clipboard is unavailable');
}

export async function shareMaxContent(content: { text: string; link: string }): Promise<'max' | 'max-web' | 'web' | 'clipboard'> {
  const webApp = getMaxWebApp();
  if (webApp?.shareMaxContent) {
    try {
      webApp.shareMaxContent(content);
      return 'max';
    } catch {
      // the bridge outside MAX cannot share: fall back to the browser below
    }
  }
  if (navigator.share) {
    await navigator.share({ text: content.text, url: content.link });
    return 'web';
  }
  const maxWindow = window.open('https://max.ru/', '_blank', 'noopener,noreferrer');
  await copyText(`${content.text}\n${content.link}`);
  return maxWindow ? 'max-web' : 'clipboard';
}

export async function openCodeReader(): Promise<string | null> {
  const webApp = getMaxWebApp();
  if (!webApp?.openCodeReader) {
    throw new Error('Сканер QR-кода доступен только внутри приложения MAX.');
  }

  try {
    // Match the official MAX example: omitted fileSelect enables camera and gallery.
    // Keep the call on WebApp so the bridge retains `this` and requestController.
    const result = await webApp.openCodeReader();
    const value = typeof result === 'string'
      ? result
      : result && typeof result === 'object' && typeof result.value === 'string'
        ? result.value
        : '';
    return value.trim() || null;
  } catch (reason) {
    const error = typeof reason === 'object' && reason !== null && 'error' in reason ? reason.error : undefined;
    const code = typeof reason === 'object' && reason !== null && 'code' in reason ? String(reason.code) : typeof error === 'object' && error !== null && 'code' in error ? String(error.code) : '';
    const nestedMessage = typeof error === 'object' && error !== null && 'message' in error ? String(error.message) : '';
    const message = reason instanceof Error ? reason.message : typeof reason === 'object' && reason !== null && 'message' in reason ? String(reason.message) : nestedMessage || String(reason);
    if (code.includes('unsupported_method') || message.includes('UnsupportedEvent')) {
      throw new Error(`Этот клиент MAX не поддерживает сканирование QR${code ? ` (${code})` : ''}. Вставьте ссылку приглашения вручную.`);
    }
    if (/cancel|dismiss|closed|user.?back/i.test(code) || /cancel|dismiss|user.?back/i.test(message)) return null;
    const detail = [code, message].filter(Boolean).join(': ').slice(0, 180);
    throw new Error(`Не удалось открыть сканер QR-кода${detail ? ` (${detail})` : ''}. Откройте приложение внутри MAX и попробуйте ещё раз.`);
  }
}

export function setQrBrightness(enabled: boolean): void {
  const app = getMaxWebApp();
  if (!app) return;
  try {
    // Same as openCodeReader: the bridge needs `this`, so never call a detached method.
    const result = enabled ? app.requestScreenMaxBrightness?.() : app.restoreScreenBrightness?.();
    void result?.catch(() => undefined);
  } catch {
    // Brightness is a convenience; it must not take the screen down.
  }
}
