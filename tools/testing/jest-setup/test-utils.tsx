/**
 * React Testing Library Utilities
 * ===============================
 *
 * Custom render function with providers and test utilities.
 * Wraps RTL with common providers (Router, Query, State, Theme).
 */

import React, { ReactElement, ReactNode } from 'react';
import {
  render as rtlRender,
  renderHook as rtlRenderHook,
  RenderOptions,
  RenderHookOptions,
  RenderResult,
} from '@testing-library/react';
import { BrowserRouter, MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// =============================================================================
// Provider Configuration Types
// =============================================================================

export interface AllProvidersOptions {
  /** Initial route for MemoryRouter */
  initialRoute?: string;
  /** Use MemoryRouter instead of BrowserRouter */
  useMemoryRouter?: boolean;
  /** Additional routes for testing navigation */
  routes?: Array<{ path: string; element: ReactElement }>;
  /** Custom QueryClient instance */
  queryClient?: QueryClient;
  /** Initial state for Zustand stores */
  initialState?: Record<string, unknown>;
  /** Additional providers to wrap */
  wrappers?: Array<React.ComponentType<{ children: ReactNode }>>;
}

// =============================================================================
// Query Client Factory
// =============================================================================

/**
 * Create a QueryClient configured for testing.
 * - Disables retries
 * - Disables garbage collection
 * - Short cache/stale times
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// =============================================================================
// Provider Wrapper
// =============================================================================

/**
 * Wrapper component with all providers.
 * Use this with RTL's wrapper option or as a standalone component.
 *
 * @example
 * render(<MyComponent />, { wrapper: AllProviders });
 *
 * @example
 * render(<MyComponent />, {
 *   wrapper: ({ children }) => (
 *     <AllProviders initialRoute="/dashboard">{children}</AllProviders>
 *   ),
 * });
 */
export function AllProviders({
  children,
  initialRoute = '/',
  useMemoryRouter = true,
  routes = [],
  queryClient,
  wrappers = [],
}: AllProvidersOptions & { children: ReactNode }): ReactElement {
  const client = queryClient ?? createTestQueryClient();

  // Build the component tree from inside out
  let content: ReactNode = children;

  // Wrap with custom wrappers (innermost first)
  for (const Wrapper of wrappers.reverse()) {
    content = <Wrapper>{content}</Wrapper>;
  }

  // Wrap with React Query
  content = <QueryClientProvider client={client}>{content}</QueryClientProvider>;

  // Wrap with Router
  if (useMemoryRouter) {
    content = (
      <MemoryRouter initialEntries={[initialRoute]}>
        {routes.length > 0 ? (
          <Routes>
            <Route path="*" element={<>{content}</>} />
            {routes.map(({ path, element }) => (
              <Route key={path} path={path} element={element} />
            ))}
          </Routes>
        ) : (
          content
        )}
      </MemoryRouter>
    );
  } else {
    content = <BrowserRouter>{content}</BrowserRouter>;
  }

  return <>{content}</>;
}

// =============================================================================
// Custom Render
// =============================================================================

export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Provider configuration options */
  providerOptions?: AllProvidersOptions;
}

/**
 * Custom render function with providers pre-configured.
 *
 * @example
 * const { getByText } = render(<MyComponent />);
 *
 * @example
 * render(<MyComponent />, {
 *   providerOptions: { initialRoute: '/users/123' }
 * });
 */
export function render(
  ui: ReactElement,
  options: CustomRenderOptions = {}
): RenderResult {
  const { providerOptions = {}, ...rtlOptions } = options;

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <AllProviders {...providerOptions}>{children}</AllProviders>
  );

  return rtlRender(ui, { wrapper: Wrapper, ...rtlOptions });
}

// =============================================================================
// Custom renderHook
// =============================================================================

export interface CustomRenderHookOptions<Props>
  extends Omit<RenderHookOptions<Props>, 'wrapper'> {
  /** Provider configuration options */
  providerOptions?: AllProvidersOptions;
}

/**
 * Custom renderHook with providers pre-configured.
 *
 * @example
 * const { result } = renderHook(() => useMyHook());
 *
 * @example
 * const { result, rerender } = renderHook(
 *   ({ id }) => useUser(id),
 *   { initialProps: { id: '123' } }
 * );
 */
export function renderHook<Result, Props>(
  hook: (props: Props) => Result,
  options: CustomRenderHookOptions<Props> = {}
): ReturnType<typeof rtlRenderHook<Result, Props>> {
  const { providerOptions = {}, ...rtlOptions } = options;

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <AllProviders {...providerOptions}>{children}</AllProviders>
  );

  return rtlRenderHook(hook, { wrapper: Wrapper, ...rtlOptions });
}

// =============================================================================
// Test Utilities
// =============================================================================

/**
 * Wait for loading states to resolve.
 * Useful when testing components with async data.
 *
 * @example
 * render(<UserList />);
 * await waitForLoading();
 * expect(screen.getByText('User 1')).toBeInTheDocument();
 */
export async function waitForLoading(
  container: HTMLElement = document.body
): Promise<void> {
  const { waitForElementToBeRemoved, queryByTestId } = await import(
    '@testing-library/react'
  );

  const spinner = queryByTestId(container, 'loading-spinner');
  if (spinner) {
    await waitForElementToBeRemoved(spinner);
  }
}

/**
 * Fill a form by label text.
 *
 * @example
 * render(<SignupForm />);
 * await fillForm({
 *   'Username': 'testuser',
 *   'Email': 'test@example.com',
 *   'Password': 'secret123',
 * });
 */
export async function fillForm(
  fields: Record<string, string>,
  container: HTMLElement = document.body
): Promise<void> {
  const { screen } = await import('@testing-library/react');
  const userEvent = (await import('@testing-library/user-event')).default;
  const user = userEvent.setup();

  for (const [label, value] of Object.entries(fields)) {
    const input = screen.getByLabelText(label);
    await user.clear(input);
    await user.type(input, value);
  }
}

/**
 * Get text content of an element without extra whitespace.
 *
 * @example
 * const text = getTextContent(screen.getByTestId('message'));
 */
export function getTextContent(element: HTMLElement): string {
  return element.textContent?.replace(/\s+/g, ' ').trim() ?? '';
}

/**
 * Debug helper - log current DOM state.
 *
 * @example
 * debugDOM(); // Logs entire document
 * debugDOM(container); // Logs specific container
 */
export function debugDOM(container: HTMLElement = document.body): void {
  const { prettyDOM } = require('@testing-library/dom');
  console.log(prettyDOM(container, Infinity));
}

// =============================================================================
// Mock Component Helpers
// =============================================================================

/**
 * Create a mock component for testing child rendering.
 *
 * @example
 * jest.mock('./ExpensiveChart', () => ({
 *   ExpensiveChart: createMockComponent('ExpensiveChart'),
 * }));
 */
export function createMockComponent(
  displayName: string
): React.FC<Record<string, unknown>> {
  const MockComponent: React.FC<Record<string, unknown>> = (props) => (
    <div data-testid={`mock-${displayName}`} data-props={JSON.stringify(props)}>
      {displayName}
    </div>
  );
  MockComponent.displayName = `Mock${displayName}`;
  return MockComponent;
}

/**
 * Create a mock hook for testing.
 *
 * @example
 * jest.mock('./useAuth', () => ({
 *   useAuth: createMockHook({ user: { id: '1' }, isAuthenticated: true }),
 * }));
 */
export function createMockHook<T>(returnValue: T): () => T {
  return jest.fn(() => returnValue);
}
