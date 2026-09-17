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

export type CompatibilityStatus = 'compatible' | 'conditional' | 'incompatible' | 'unknown';
export type EvidenceLevel = 'ci_verified' | 'vendor_tested' | 'community_reported' | 'inferred' | 'unknown';

export interface EnvironmentTarget {
  ros_version?: string;
  os?: string;
  os_version?: string;
  cpu_architecture?: string;
  capabilities?: string[];
  hardware?: string[];
}

export interface RuleEvaluation {
  rule_name: string;
  status: CompatibilityStatus;
  message: string;
  evidence_level: EvidenceLevel;
  remediation?: string;
}

export interface ConflictDetail {
  source_id: string;
  target_id?: string;
  conflict_type: string;
  message: string;
  dependency_path: string[];
  remediation?: string;
}

export interface CompatibilityResult {
  status: CompatibilityStatus;
  resource_ids: string[];
  environment?: EnvironmentTarget;
  rule_evaluations: RuleEvaluation[];
  conflicts: ConflictDetail[];
  warnings: string[];
  missing_requirements: string[];
  dependency_paths: string[][];
  evidence_level: EvidenceLevel;
  remediation?: string;
  evaluated_at: string;
}

export interface ResourceCompatibilityProfile {
  resource_id: string;
  name: string;
  version?: string;
  type: string;
  evidence_level: string;
  direct_dependencies: string[];
  provides: string[];
  requires: string[];
  tested_with: string[];
  compatible_with: string[];
  conflicts_with: string[];
  platform_matrix: Record<string, string[]>;
}

export interface CompatibilityMatrixResponse {
  candidate_ids: string[];
  matrix: Record<string, Record<string, CompatibilityResult>>;
  summary: Record<string, number>;
  evaluated_at: string;
}
