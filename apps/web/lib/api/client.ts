import {
  CompatibilityMatrixResponse,
  CompatibilityResult,
  EnvironmentTarget,
  ResolutionProposal,
  Resource,
  ResourceCompatibilityProfile,
  ResourceListResult,
  ResourceQueryParams,
  SearchFacetDistribution,
  SearchResponse,
  Stack,
  StackComponent,
  StackCreateInput,
  StackImportResult,
  StackTemplate,
  StackUpdateInput,
  StackValidationResponse,
  WorkspacePreviewResponse,
  WorkspaceRequest,
  ExecutionProviderInfo,
  RosEnvironmentInfo,
  ConnectionInspectorReport,
  SimulatorInfo,
  RuntimeVerificationResult,
  RuntimeSession,
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
  const searchRes = await searchResources(params);
  return {
    items: searchRes.items.map((hit) => hit.resource),
    total: searchRes.total,
    limit: searchRes.limit,
    offset: searchRes.offset,
  };
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

export async function fetchResourceCompatibilityProfile(
  resourceId: string
): Promise<ResourceCompatibilityProfile> {
  const encodedId = encodeURIComponent(resourceId);
  const url = `${API_BASE_URL}/api/v1/compatibility/resource/${encodedId}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new ApiError(`Failed to fetch compatibility profile: HTTP ${res.status}`, res.status);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(`Unable to evaluate compatibility profile for '${resourceId}'.`, undefined, true);
  }
}

export async function evaluateCompatibility(
  resourceIds: string[],
  environment?: EnvironmentTarget
): Promise<CompatibilityResult> {
  const url = `${API_BASE_URL}/api/v1/compatibility/evaluate`;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        resource_ids: resourceIds,
        environment,
      }),
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new ApiError(`Compatibility evaluation failed: HTTP ${res.status}`, res.status);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to evaluate compatibility stack.', undefined, true);
  }
}

export async function fetchCompatibilityMatrix(
  resourceIds: string[],
  environment?: EnvironmentTarget
): Promise<CompatibilityMatrixResponse> {
  const url = `${API_BASE_URL}/api/v1/compatibility/matrix`;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        resource_ids: resourceIds,
        environment,
      }),
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new ApiError(`Failed to fetch compatibility matrix: HTTP ${res.status}`, res.status);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to fetch compatibility matrix.', undefined, true);
  }
}

// ---------------- STACK BUILDER APIS ----------------

export async function fetchStackTemplates(): Promise<StackTemplate[]> {
  const url = `${API_BASE_URL}/api/v1/stacks/templates`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Failed to fetch templates: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to reach OpenRobo Stacks API for templates.', undefined, true);
  }
}

export async function validateAdhocStack(payload: {
  components: StackComponent[];
  target_os?: string;
  target_arch?: string;
  target_ros_distro?: string;
}): Promise<StackValidationResponse> {
  const url = `${API_BASE_URL}/api/v1/stacks/validate`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload),
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Stack validation failed: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to validate stack with backend engine.', undefined, true);
  }
}

export async function resolveAdhocStack(payload: {
  components: StackComponent[];
  target_os?: string;
  target_arch?: string;
  target_ros_distro?: string;
}): Promise<ResolutionProposal> {
  const url = `${API_BASE_URL}/api/v1/stacks/resolve`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload),
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Stack resolution failed: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to resolve stack dependencies.', undefined, true);
  }
}

export async function fetchStacks(params: { q?: string; domain?: string; limit?: number; offset?: number } = {}): Promise<Stack[]> {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set('q', params.q);
  if (params.domain) searchParams.set('domain', params.domain);
  if (params.limit) searchParams.set('limit', params.limit.toString());
  if (params.offset !== undefined) searchParams.set('offset', params.offset.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/stacks${queryString ? `?${queryString}` : ''}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Failed to fetch stacks: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to fetch stacks from backend.', undefined, true);
  }
}

export async function fetchStackById(id: string): Promise<Stack> {
  const url = `${API_BASE_URL}/api/v1/stacks/${id}`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Stack '${id}' not found: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(`Unable to fetch stack '${id}'.`, undefined, true);
  }
}

export async function createStack(input: StackCreateInput): Promise<Stack> {
  const url = `${API_BASE_URL}/api/v1/stacks`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(input),
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Failed to create stack: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to create stack on backend.', undefined, true);
  }
}

export async function updateStack(id: string, input: StackUpdateInput): Promise<Stack> {
  const url = `${API_BASE_URL}/api/v1/stacks/${id}`;
  try {
    const res = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(input),
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Failed to update stack: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(`Unable to update stack '${id}'.`, undefined, true);
  }
}

export async function deleteStack(id: string): Promise<void> {
  const url = `${API_BASE_URL}/api/v1/stacks/${id}`;
  try {
    const res = await fetch(url, {
      method: 'DELETE',
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Failed to delete stack: HTTP ${res.status}`, res.status);
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(`Unable to delete stack '${id}'.`, undefined, true);
  }
}

export async function fetchStackManifest(id: string): Promise<Record<string, unknown>> {
  const url = `${API_BASE_URL}/api/v1/stacks/${id}/manifest`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Failed to export stack manifest: HTTP ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to export stack manifest.', undefined, true);
  }
}

export async function importStackManifest(manifest: Record<string, unknown>): Promise<StackImportResult> {
  const url = `${API_BASE_URL}/api/v1/stacks/import`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ manifest }),
      cache: 'no-store',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err?.detail?.message || `Import failed with HTTP ${res.status}`, res.status);
    }
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to import stack manifest.', undefined, true);
  }
}

export async function previewWorkspace(req: WorkspaceRequest): Promise<WorkspacePreviewResponse> {
  const url = `${API_BASE_URL}/api/v1/workspace/preview`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(req),
      cache: 'no-store',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err?.detail || `Preview failed: HTTP ${res.status}`, res.status);
    }
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to preview workspace generation.', undefined, true);
  }
}

export async function downloadWorkspaceZip(req: WorkspaceRequest): Promise<Blob> {
  const url = `${API_BASE_URL}/api/v1/workspace/download`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/zip' },
      body: JSON.stringify(req),
      cache: 'no-store',
    });
    if (!res.ok) {
      throw new ApiError(`Download failed: HTTP ${res.status}`, res.status);
    }
    return await res.blob();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to download workspace archive.', undefined, true);
  }
}
export async function fetchProviders(): Promise<Record<string, ExecutionProviderInfo>> {
  const url = `${API_BASE_URL}/api/v1/runtime/providers`;
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new ApiError(`Providers fetch failed: ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to connect to OpenRobo Runtime API.', undefined, true);
  }
}

export async function fetchRosEnvironment(): Promise<RosEnvironmentInfo> {
  const url = `${API_BASE_URL}/api/v1/runtime/environment`;
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new ApiError(`Environment fetch failed: ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to detect ROS environment.', undefined, true);
  }
}

export async function fetchConnectionInspector(distro?: string): Promise<ConnectionInspectorReport> {
  const query = distro ? `?distro=${encodeURIComponent(distro)}` : '';
  const url = `${API_BASE_URL}/api/v1/runtime/connection-inspector${query}`;
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new ApiError(`Connection Inspector status failed: ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to inspect Connection Inspector tool.', undefined, true);
  }
}

export async function fetchSimulators(): Promise<Record<string, SimulatorInfo>> {
  const url = `${API_BASE_URL}/api/v1/runtime/simulators`;
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new ApiError(`Simulators fetch failed: ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to inspect simulation adapters.', undefined, true);
  }
}

export async function fetchLiveGraph(): Promise<{ status: string; nodes: any[]; topics: any[] }> {
  const url = `${API_BASE_URL}/api/v1/runtime/introspection/live`;
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new ApiError(`Live graph collection failed: ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to query live ROS graph.', undefined, true);
  }
}

export async function compareRuntimeGraph(payload: {
  planned_manifest: Record<string, unknown>;
  observed_nodes?: any[];
  observed_topics?: any[];
  observed_tfs?: any[];
  runtime_contract?: any;
}): Promise<RuntimeVerificationResult> {
  const url = `${API_BASE_URL}/api/v1/runtime/introspection/compare`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      cache: 'no-store',
    });
    if (!res.ok) throw new ApiError(`Comparison failed: ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to compare runtime graph.', undefined, true);
  }
}

export async function fetchRuntimeSessions(): Promise<RuntimeSession[]> {
  const url = `${API_BASE_URL}/api/v1/runtime/sessions`;
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new ApiError(`Sessions fetch failed: ${res.status}`, res.status);
    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to fetch runtime sessions.', undefined, true);
  }
}
