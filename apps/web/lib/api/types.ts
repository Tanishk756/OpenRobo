export interface SourceDetail {
  repo_url: string;
  vcs_type?: string;
  branch?: string;
  commit?: string;
}

export interface LicenseDetail {
  spdx_id: string;
  license_url?: string;
}

export interface PlatformDetail {
  operating_systems?: string[];
  cpu_architectures?: string[];
  ros_versions?: string[];
}

export interface EvidenceDetail {
  level: string;
  notes?: string;
}

export interface ProvenanceDetail {
  source_provider?: string;
  source_url?: string;
  source_identifier?: string;
  upstream_revision?: string;
  ingestion_timestamp?: string;
  provenance_classification?: string;
  source_manifest_path?: string;
  inspected_files?: string[];
  maintainers?: string[];
}

export interface ResourceMetadata {
  provenance?: ProvenanceDetail;
  dependencies?: Record<string, string[]>;
  sub_packages?: string[];
}

export interface Resource {
  id: string;
  name: string;
  version?: string;
  type: string;
  summary?: string;
  description?: string;
  spdx_license_id: string;
  repo_url?: string;
  evidence_level?: string;
  robotics_domains?: string[];
  capabilities?: string[];
  platforms?: PlatformDetail;
  source?: SourceDetail;
  license?: LicenseDetail;
  evidence?: EvidenceDetail;
  metadata_json?: ResourceMetadata;
  score?: number;
  highlight?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ResourceQueryParams {
  q?: string;
  type?: string;
  domain?: string;
  capability?: string;
  ecosystem?: string;
  license?: string;
  ros_version?: string;
  os?: string;
  limit?: number;
  offset?: number;
  fuzzy?: boolean;
}

export interface ResourceListResult {
  items: Resource[];
  total: number;
  limit: number;
  offset: number;
}

export interface SearchFacetDistribution {
  types?: Record<string, number>;
  domains?: Record<string, number>;
  capabilities?: Record<string, number>;
  licenses?: Record<string, number>;
  ros_versions?: Record<string, number>;
}

export interface SearchResultHit {
  resource: Resource;
  score: number;
  highlights: Record<string, string[]>;
}

export interface SearchResponse {
  query?: string;
  total: number;
  limit: number;
  offset: number;
  items: SearchResultHit[];
  facets: SearchFacetDistribution;
}
