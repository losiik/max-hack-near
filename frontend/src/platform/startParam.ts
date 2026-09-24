export type LaunchIntent =
  | { kind: 'home' }
  | { kind: 'assist_invite'; token: string }
  | { kind: 'invite_declined'; token: string }
  | { kind: 'helper_ready'; callbackId: string }
  | { kind: 'pairing'; token: string }
  | { kind: 'unknown'; value: string };

export function parseStartParam(value: string): LaunchIntent {
  if (!value) return { kind: 'home' };
  if (value.startsWith('as_')) return { kind: 'assist_invite', token: value.slice(3) };
  if (value.startsWith('ad_')) return { kind: 'invite_declined', token: value.slice(3) };
  if (value.startsWith('ar_')) return { kind: 'helper_ready', callbackId: value.slice(3) };
  if (value.startsWith('pr_')) return { kind: 'pairing', token: value.slice(3) };
  return { kind: 'unknown', value };
}

export function launchIntentLabel(intent: LaunchIntent): string {
  switch (intent.kind) {
    case 'assist_invite':
      return 'Приглашение помочь';
    case 'invite_declined':
      return 'Ответить «Сейчас занят»';
    case 'helper_ready':
      return 'Сообщить, что вы освободились';
    case 'pairing':
      return 'Стать доверенным помощником';
    case 'unknown':
      return 'Неизвестная ссылка';
    default:
      return 'Главная';
  }
}
