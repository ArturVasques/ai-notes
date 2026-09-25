import { HttpErrorResponse } from '@angular/common/http';

/** Human-readable message for a failed API call, without internals. */
export function errorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const body = error.error as { message?: unknown; detail?: unknown } | null;

    if (body && typeof body.message === 'string') {
      return body.message;
    }

    if (body && typeof body.detail === 'string') {
      return body.detail;
    }

    if (error.status === 0) {
      return 'The API is unreachable.';
    }

    if (error.status === 401) {
      return 'Your session has expired. Please sign in again.';
    }

    if (error.status === 422) {
      return 'Some values are not valid.';
    }

    return `Request failed (${error.status}).`;
  }

  return 'Something went wrong.';
}
