import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button, Flex, Typography } from '@maxhub/max-ui';

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  error: Error | null;
  componentStack: string;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { error: null, componentStack: '' };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error, componentStack: '' };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Application render error', error, info.componentStack);
    this.setState({ componentStack: info.componentStack ?? '' });
  }

  render() {
    if (!this.state.error) return this.props.children;

    const isHookOrderError = /#310|more hooks than during the previous render/i.test(this.state.error.message);
    const message = isHookOrderError
      ? 'Ошибка интерфейса: компоненты вызвали React-хуки в разном порядке. Обновите приложение после выкладки новой версии.'
      : this.state.error.message || 'Произошла ошибка интерфейса.';
    const details = [
      `message: ${this.state.error.message || 'unknown'}`,
      `url: ${window.location.href}`,
      this.state.componentStack ? `component stack:\n${this.state.componentStack}` : '',
    ].filter(Boolean).join('\n\n');

    return <Flex direction="column" gap={12} className="screen-center app-error-screen">
      <Typography.Title>Не удалось открыть приложение</Typography.Title>
      <Typography.Text>{message}</Typography.Text>
      <details className="app-error-details">
        <summary>Технические подробности</summary>
        <pre>{details}</pre>
      </details>
      <Button size="small" onClick={() => window.location.reload()}>Повторить</Button>
    </Flex>;
  }
}
