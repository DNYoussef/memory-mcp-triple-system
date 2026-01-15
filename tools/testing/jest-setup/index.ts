/**
 * Jest Setup Library Component
 * ============================
 *
 * LEGO-compatible Jest + React Testing Library setup for React 18/19 projects.
 * Provides reusable configuration, custom render, and test utilities.
 *
 * @example
 * // In your jest.setup.ts
 * import '@testing-library/jest-dom';
 * import { setupMocks, configure } from 'jest-setup';
 * configure({ enableMSW: true });
 * setupMocks();
 *
 * @example
 * // In your test files
 * import { render, screen, userEvent } from 'jest-setup/test-utils';
 * import { Button } from '../Button';
 *
 * test('button click', async () => {
 *   const onClick = jest.fn();
 *   render(<Button onClick={onClick}>Click me</Button>);
 *   await userEvent.click(screen.getByRole('button'));
 *   expect(onClick).toHaveBeenCalled();
 * });
 */

export { configure, setupMocks, cleanupMocks } from './setup';
export { render, renderHook, AllProviders } from './test-utils';
export {
  toBeValidJSON,
  toHaveBeenCalledWithMatch,
  toBeWithinRange,
  toMatchAPIResponse,
} from './matchers';

// Re-export commonly used RTL utilities
export {
  screen,
  waitFor,
  within,
  fireEvent,
  cleanup,
} from '@testing-library/react';

export { default as userEvent } from '@testing-library/user-event';
