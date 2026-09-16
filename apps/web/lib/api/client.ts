import { Resource, ResourceListResult, ResourceQueryParams } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status?: number;
  isNetworkError: boolean;

  constructor(message: string, status?: number, isNetworkError: boolean = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.isNetworkError = isNetworkError;
  }
}

export async function fetchResources(params: ResourceQueryParams = {}): Promise<ResourceListResult> {
  const searchParams = new URLSearchParams();

  if (params.q && params.q.trim()) searchParams.set('q', params.q.trim());
  if (params.type && params.type.trim()) searchParams.set('type', params.type.trim());
  if (params.domain && params.domain.trim()) searchParams.set('domain', params.domain.trim());
  if (params.capability && params.capability.trim()) searchParams.set('capability', params.capability.trim());
  if (params.ecosystem && params.ecosystem.trim()) searchParams.set('ecosystem', params.ecosystem.trim());
  if (params.limit) searchParams.set('limit', params.limit.toString());
  if (params.offset !== undefined) searchParams.set('offset', params.offset.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/resources${queryString ? `?${queryString}` : ''}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      const errorText = await res.text().catch(() => 'Unknown error');
      throw new ApiError(`API responded with status ${res.status}: ${errorText}`, res.status);
    }

    const totalHeader = res.headers.get('X-Total-Count');
    const limitHeader = res.headers.get('X-Limit');
    const offsetHeader = res.headers.get('X-Offset');

    const items: Resource[] = await res.json();
    const total = totalHeader ? parseInt(totalHeader, 10) : items.length;
    const limit = limitHeader ? parseInt(limitHeader, 10) : (params.limit || 50);
    const offset = offsetHeader ? parseInt(offsetHeader, 10) : (params.offset || 0);

    return { items, total, limit, offset };
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      `Unable to connect to OpenRobo Registry API at ${API_BASE_URL}. Ensure the backend service is running.`,
      undefined,
      true
    );
  }
}

export async function fetchResourceById(resourceId: string): Promise<Resource> {
  const encodedId = encodeURIComponent(resourceId);
  const url = `${API_BASE_URL}/api/v1/resources/${encodedId}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      if (res.status === 404) {
        throw new ApiError(`Resource '${resourceId}' not found in registry.`, 404);
      }
      throw new ApiError(`Failed to fetch resource '${resourceId}': HTTP ${res.status}`, res.status);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      `Unable to reach OpenRobo Registry API for resource '${resourceId}'.`,
      undefined,
      true
    );
  }
}
