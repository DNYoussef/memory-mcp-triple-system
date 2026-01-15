/**
 * Custom Jest Matchers
 * ====================
 *
 * Additional Jest matchers for common testing patterns.
 * Import and extend in your jest.setup.ts.
 *
 * @example
 * // In jest.setup.ts
 * import { matchers } from 'jest-setup/matchers';
 * expect.extend(matchers);
 *
 * // In tests
 * expect('{"valid": true}').toBeValidJSON();
 * expect(mockFn).toHaveBeenCalledWithMatch({ id: expect.any(String) });
 */

import { expect } from '@jest/globals';

// =============================================================================
// Matcher Types
// =============================================================================

declare global {
  namespace jest {
    interface Matchers<R> {
      /** Check if string is valid JSON */
      toBeValidJSON(): R;
      /** Check if mock was called with object matching partial */
      toHaveBeenCalledWithMatch(expected: Record<string, unknown>): R;
      /** Check if number is within range (inclusive) */
      toBeWithinRange(min: number, max: number): R;
      /** Check if value matches API response structure */
      toMatchAPIResponse(expected: { status?: number; data?: unknown }): R;
      /** Check if element has specific CSS class */
      toHaveClass(className: string): R;
      /** Check if promise resolves within timeout */
      toResolveWithin(timeout: number): Promise<R>;
      /** Check if array is sorted */
      toBeSorted(compareFn?: (a: unknown, b: unknown) => number): R;
      /** Check if object has all keys */
      toHaveKeys(keys: string[]): R;
    }
  }
}

// =============================================================================
// Matcher Implementations
// =============================================================================

/**
 * Check if string is valid JSON.
 *
 * @example
 * expect('{"valid": true}').toBeValidJSON(); // passes
 * expect('not json').toBeValidJSON(); // fails
 */
export function toBeValidJSON(
  this: jest.MatcherContext,
  received: unknown
): jest.CustomMatcherResult {
  if (typeof received !== 'string') {
    return {
      pass: false,
      message: () =>
        `Expected ${this.utils.printReceived(received)} to be a string`,
    };
  }

  try {
    JSON.parse(received);
    return {
      pass: true,
      message: () =>
        `Expected ${this.utils.printReceived(received)} not to be valid JSON`,
    };
  } catch {
    return {
      pass: false,
      message: () =>
        `Expected ${this.utils.printReceived(received)} to be valid JSON`,
    };
  }
}

/**
 * Check if mock was called with object matching partial structure.
 *
 * @example
 * mockFn({ id: '123', name: 'test', timestamp: Date.now() });
 * expect(mockFn).toHaveBeenCalledWithMatch({ id: '123' }); // passes
 */
export function toHaveBeenCalledWithMatch(
  this: jest.MatcherContext,
  received: jest.Mock,
  expected: Record<string, unknown>
): jest.CustomMatcherResult {
  if (!jest.isMockFunction(received)) {
    return {
      pass: false,
      message: () =>
        `Expected ${this.utils.printReceived(received)} to be a mock function`,
    };
  }

  const calls = received.mock.calls;
  const matchingCall = calls.find((call) => {
    const arg = call[0];
    if (typeof arg !== 'object' || arg === null) return false;

    return Object.entries(expected).every(([key, value]) => {
      if (this.equals(arg[key], value)) return true;
      // Support jest matchers like expect.any(String)
      if (
        typeof value === 'object' &&
        value !== null &&
        'asymmetricMatch' in value
      ) {
        return (value as { asymmetricMatch: (v: unknown) => boolean }).asymmetricMatch(
          arg[key]
        );
      }
      return false;
    });
  });

  return {
    pass: !!matchingCall,
    message: () =>
      matchingCall
        ? `Expected mock not to have been called with object matching ${this.utils.printExpected(
            expected
          )}`
        : `Expected mock to have been called with object matching ${this.utils.printExpected(
            expected
          )}\nReceived calls: ${this.utils.printReceived(calls)}`,
  };
}

/**
 * Check if number is within range (inclusive).
 *
 * @example
 * expect(5).toBeWithinRange(1, 10); // passes
 * expect(15).toBeWithinRange(1, 10); // fails
 */
export function toBeWithinRange(
  this: jest.MatcherContext,
  received: unknown,
  min: number,
  max: number
): jest.CustomMatcherResult {
  if (typeof received !== 'number') {
    return {
      pass: false,
      message: () =>
        `Expected ${this.utils.printReceived(received)} to be a number`,
    };
  }

  const pass = received >= min && received <= max;
  return {
    pass,
    message: () =>
      pass
        ? `Expected ${this.utils.printReceived(received)} not to be within range ${min} - ${max}`
        : `Expected ${this.utils.printReceived(received)} to be within range ${min} - ${max}`,
  };
}

/**
 * Check if value matches API response structure.
 *
 * @example
 * expect(response).toMatchAPIResponse({ status: 200, data: { id: '1' } });
 */
export function toMatchAPIResponse(
  this: jest.MatcherContext,
  received: unknown,
  expected: { status?: number; data?: unknown; ok?: boolean }
): jest.CustomMatcherResult {
  if (typeof received !== 'object' || received === null) {
    return {
      pass: false,
      message: () =>
        `Expected ${this.utils.printReceived(received)} to be an object`,
    };
  }

  const response = received as Record<string, unknown>;
  const checks: string[] = [];

  if (expected.status !== undefined && response.status !== expected.status) {
    checks.push(`status: expected ${expected.status}, got ${response.status}`);
  }

  if (expected.ok !== undefined && response.ok !== expected.ok) {
    checks.push(`ok: expected ${expected.ok}, got ${response.ok}`);
  }

  if (expected.data !== undefined && !this.equals(response.data, expected.data)) {
    checks.push(
      `data: expected ${this.utils.printExpected(expected.data)}, got ${this.utils.printReceived(response.data)}`
    );
  }

  return {
    pass: checks.length === 0,
    message: () =>
      checks.length === 0
        ? `Expected response not to match API response structure`
        : `Expected response to match API response structure:\n${checks.join('\n')}`,
  };
}

/**
 * Check if array is sorted.
 *
 * @example
 * expect([1, 2, 3]).toBeSorted(); // passes
 * expect(['a', 'b', 'c']).toBeSorted(); // passes
 * expect([3, 1, 2]).toBeSorted(); // fails
 */
export function toBeSorted(
  this: jest.MatcherContext,
  received: unknown,
  compareFn?: (a: unknown, b: unknown) => number
): jest.CustomMatcherResult {
  if (!Array.isArray(received)) {
    return {
      pass: false,
      message: () =>
        `Expected ${this.utils.printReceived(received)} to be an array`,
    };
  }

  const defaultCompare = (a: unknown, b: unknown): number => {
    if (a === b) return 0;
    return a < b ? -1 : 1;
  };

  const compare = compareFn ?? defaultCompare;
  const sorted = [...received].sort(compare);
  const pass = this.equals(received, sorted);

  return {
    pass,
    message: () =>
      pass
        ? `Expected array not to be sorted`
        : `Expected array to be sorted\nReceived: ${this.utils.printReceived(received)}\nExpected: ${this.utils.printExpected(sorted)}`,
  };
}

/**
 * Check if object has all specified keys.
 *
 * @example
 * expect({ a: 1, b: 2, c: 3 }).toHaveKeys(['a', 'b']); // passes
 * expect({ a: 1 }).toHaveKeys(['a', 'b']); // fails
 */
export function toHaveKeys(
  this: jest.MatcherContext,
  received: unknown,
  keys: string[]
): jest.CustomMatcherResult {
  if (typeof received !== 'object' || received === null) {
    return {
      pass: false,
      message: () =>
        `Expected ${this.utils.printReceived(received)} to be an object`,
    };
  }

  const obj = received as Record<string, unknown>;
  const missingKeys = keys.filter((key) => !(key in obj));

  return {
    pass: missingKeys.length === 0,
    message: () =>
      missingKeys.length === 0
        ? `Expected object not to have keys ${this.utils.printExpected(keys)}`
        : `Expected object to have keys ${this.utils.printExpected(keys)}\nMissing: ${this.utils.printReceived(missingKeys)}`,
  };
}

// =============================================================================
// Matcher Export
// =============================================================================

/**
 * All custom matchers bundled for expect.extend().
 *
 * @example
 * import { matchers } from 'jest-setup/matchers';
 * expect.extend(matchers);
 */
export const matchers = {
  toBeValidJSON,
  toHaveBeenCalledWithMatch,
  toBeWithinRange,
  toMatchAPIResponse,
  toBeSorted,
  toHaveKeys,
};

// Auto-extend if in Jest environment
if (typeof expect !== 'undefined' && typeof expect.extend === 'function') {
  expect.extend(matchers);
}
