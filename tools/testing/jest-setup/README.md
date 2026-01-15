# Jest Setup Library Component

LEGO-compatible Jest + React Testing Library setup for React 18/19 projects with TypeScript.

## Installation

### 1. Install Dependencies

```bash
npm install -D jest @types/jest ts-jest @testing-library/react @testing-library/jest-dom @testing-library/user-event @tanstack/react-query react-router-dom
```

### 2. Copy to Project

```bash
cp -r jest-setup/ your_project/src/test-utils/
```

### 3. Configure Jest

Create `jest.config.ts`:

```typescript
import type { Config } from 'jest';

const config: Config = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/test-utils/jest-setup/setup.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^jest-setup/(.*)$': '<rootDir>/src/test-utils/jest-setup/$1',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: 'tsconfig.json' }],
  },
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
};

export default config;
```

## Quick Start

```typescript
import { render, screen } from 'jest-setup/test-utils';
import userEvent from '@testing-library/user-event';
import { Button } from '../Button';

test('button click', async () => {
  const onClick = jest.fn();
  render(<Button onClick={onClick}>Click me</Button>);
  await userEvent.click(screen.getByRole('button'));
  expect(onClick).toHaveBeenCalled();
});
```

## Custom Matchers

```typescript
expect('{"valid": true}').toBeValidJSON();
expect(mockFn).toHaveBeenCalledWithMatch({ id: expect.any(String) });
expect(5).toBeWithinRange(1, 10);
expect(response).toMatchAPIResponse({ status: 200 });
expect([1, 2, 3]).toBeSorted();
expect(obj).toHaveKeys(['id', 'name']);
```

## Built-in Mocks

| API | Mock Behavior |
|-----|---------------|
| ResizeObserver | Triggers callback immediately |
| IntersectionObserver | Reports element as visible |
| localStorage | In-memory storage |
| sessionStorage | In-memory storage |
| matchMedia | Returns matches: false |
| scrollTo | No-op |
| fetch | Returns empty successful response |

## File Structure

```
jest-setup/
  index.ts       # Package exports
  setup.ts       # Global setup and mocks
  test-utils.tsx # Custom render with providers
  matchers.ts    # Custom Jest matchers
  README.md      # This documentation
```

## Version

1.0.0 - Initial creation based on RTL best practices
