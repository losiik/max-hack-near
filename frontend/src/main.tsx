import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MaxUI } from '@maxhub/max-ui';
import { QueryClientProvider } from '@tanstack/react-query';
import '@maxhub/max-ui/dist/styles.css';
import './styles.css';
import App from './App';
import { queryClient } from './app/queryClient';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MaxUI>
        <App />
      </MaxUI>
    </QueryClientProvider>
  </StrictMode>,
);
