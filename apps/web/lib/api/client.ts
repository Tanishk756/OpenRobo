import {
  Resource,
  ResourceListResult,
  ResourceQueryParams,
  SearchFacetDistribution,
  SearchResponse,
} from './types';

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

export async function searchResources(params: ResourceQueryParams = {}): Promise<SearchResponse> {
  const searchParams = new URLSearchParams();

  if (params.q && params.q.trim()) searchParams.set('q', params.q.trim());
  if (params.type && params.type.trim()) searchParams.set('type', params.type.trim());
  if (params.domain && params.domain.trim()) searchParams.set('domain', params.domain.trim());
  if (params.capability && params.capability.trim()) searchParams.set('capability', params.capability.trim());
  if (params.ecosystem && params.ecosystem.trim()) searchParams.set('ecosystem', params.ecosystem.trim());
  if (params.license && params.license.trim()) searchParams.set('license', params.license.trim());
  if (params.ros_version && params.ros_version.trim()) searchParams.set('ros_version', params.ros_version.trim());
  if (params.os && params.os.trim()) searchParams.set('os', params.os.trim());
  if (params.limit) searchParams.set('limit', params.limit.toString());
  if (params.offset !== undefined) searchParams.set('offset', params.offset.toString());
  if (params.fuzzy !== undefined) searchParams.set('fuzzy', params.fuzzy.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/search${queryString ? `?${queryString}` : ''}`;

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

    const data: SearchResponse = await res.json();
    return data;
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      `Unable to connect to OpenRobo Search API at ${API_BASE_URL}. Ensure the backend service is running.`,
      undefined,
      true
    );
  }
}

export async function fetchSearchFacets(q?: string): Promise<SearchFacetDistribution> {
  const searchParams = new URLSearchParams();
  if (q && q.trim()) searchParams.set('q', q.trim());
  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/search/facets${queryString ? `?${queryString}` : ''}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new ApiError(`Failed to fetch facets: HTTP ${res.status}`, res.status);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      `Unable to reach OpenRobo Facets API at ${API_BASE_URL}.`,
      undefined,
      true
    );
  }
}

export async function fetchResources(params: ResourceQueryParams = {}): Promise<ResourceListResult> {
  // Use searchResources under the hood for unified search, faceting, and filtering
  try {
    const searchRes = await searchResources(params);
    return {
      items: searchRes.items.map((hit) => hit.resource),
      total: searchRes.total,
      limit: searchRes.limit,
      offset: searchRes.offset,
    };
  } catch (err) {
    throw err;
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
