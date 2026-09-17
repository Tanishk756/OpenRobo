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
  ros_distribution?: string;
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

export interface StackComponent {
  resource_id: string;
  version?: string;
  category?: string;
  optional?: boolean;
  notes?: string;
  configuration?: Record<string, unknown>;
}

export interface Stack {
  id: string;
  name: string;
  version: string;
  description?: string;
  robot_domain: string;
  robot_type: string;
  target_os?: string;
  target_arch?: string;
  target_ros_distro?: string;
  components: StackComponent[];
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StackCreateInput {
  name: string;
  version?: string;
  description?: string;
  robot_domain?: string;
  robot_type?: string;
  target_os?: string;
  target_arch?: string;
  target_ros_distro?: string;
  components?: StackComponent[];
  metadata?: Record<string, unknown>;
}

export interface StackUpdateInput {
  name?: string;
  version?: string;
  description?: string;
  robot_domain?: string;
  robot_type?: string;
  target_os?: string;
  target_arch?: string;
  target_ros_distro?: string;
  components?: StackComponent[];
  metadata?: Record<string, unknown>;
}

export interface ProposedComponentAction {
  action: 'add_component' | 'remove_component' | 'change_version';
  resource_id: string;
  name: string;
  version?: string;
  category?: string;
  reason: string;
  required_by?: string;
  optional?: boolean;
}

export interface ResolutionProposal {
  is_fully_resolved: boolean;
  missing_mandatory_count: number;
  missing_optional_count: number;
  proposed_actions: ProposedComponentAction[];
  conflicts: ConflictDetail[];
  warnings: string[];
  summary: string;
}

export interface StackValidationResponse {
  stack_id?: string;
  status: CompatibilityStatus;
  total_components: number;
  verified_compatible_count: number;
  conditional_count: number;
  incompatible_count: number;
  unknown_count: number;
  missing_dependencies_count: number;
  version_conflicts_count: number;
  cycles_count: number;
  compatibility_result: CompatibilityResult;
  resolution_proposal?: ResolutionProposal;
  evaluated_at: string;
}

export interface StackTemplate {
  id: string;
  name: string;
  title: string;
  description: string;
  robot_domain: string;
  robot_type: string;
  target_os: string;
  target_arch: string;
  target_ros_distro: string;
  components: StackComponent[];
  metadata?: Record<string, unknown>;
}

export interface StackImportResult {
  manifest: Record<string, unknown>;
  unavailable_resources: string[];
  validation: StackValidationResponse;
  is_valid: boolean;
}

export interface FileTreeNode {
  name: string;
  path?: string;
  type: 'file' | 'directory';
  size?: number;
  is_executable?: boolean;
  description?: string;
  children?: Record<string, FileTreeNode>;
}

export interface WorkspaceReadinessReport {
  overall_state: string;
  static_validation: string;
  docker_build: string;
  colcon_build: string;
  runtime_validation: string;
  manual_steps_required: string[];
  evidence_summary: Record<string, string>;
  notes: string[];
}

export interface WorkspaceValidationResult {
  is_valid: boolean;
  status: string;
  checks_count: number;
  errors: string[];
  warnings: string[];
}

export interface WorkspacePreviewResponse {
  status: string;
  stack_id: string;
  stack_name: string;
  workspace_name: string;
  target_distro: string;
  target_os: string;
  target_arch: string;
  compatibility_verdict: string;
  file_count: number;
  total_bytes: number;
  file_tree: FileTreeNode;
  files: Record<string, string>;
  warnings: string[];
  unsupported_components: string[];
  selected_adapters: string[];
  generator_version: string;
  generated_at: string;
  readiness_report?: WorkspaceReadinessReport;
  validation_result?: WorkspaceValidationResult;
}

export interface WorkspaceRequest {
  stack_id?: string;
  manifest?: Record<string, unknown>;
  allow_incompatible?: boolean;
}

// ==========================================
// Milestone 6 & 6.1: Live Runtime & Verification Models
// ==========================================

export type RosEnvironmentStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'MISCONFIGURED';

export interface RosEnvironmentInfo {
  status: RosEnvironmentStatus;
  ros_distro?: string | null;
  ros_version?: number | null;
  rmw_implementation?: string | null;
  ros_domain_id?: number | null;
  rclpy_available: boolean;
  ros2_cli_available: boolean;
  installation_prefix?: string | null;
  details?: string | null;
}

export type DistroReleaseSupport = 'VERIFIED_RELEASE' | 'UNKNOWN' | 'UNSUPPORTED';

export interface ConnectionInspectorReport {
  status: 'AVAILABLE' | 'NOT_INSTALLED' | 'UNKNOWN_DISTRO' | 'EXECUTION_FAILED' | 'MISSING_EXECUTABLE';
  version?: string | null;
  distro?: string | null;
  release_support?: DistroReleaseSupport;
  executables: string[];
  licensing_notice: string;
  details?: string | null;
}

export interface ExecutionProviderInfo {
  provider_type: string;
  status: 'AVAILABLE' | 'UNAVAILABLE' | 'DETECTED_NOT_IMPLEMENTED';
  details?: string;
  supports_build_verification?: boolean;
}

export interface SimulatorInfo {
  simulator: string;
  installed: boolean;
  version?: string | null;
  details?: string | null;
}

export interface NodeHealth {
  name: string;
  namespace: string;
  full_name?: string;
  is_present: boolean;
  is_alive: boolean;
  pid?: number | null;
  publisher_topics: string[];
  subscriber_topics: string[];
  services: string[];
  actions: string[];
}

export interface ConnectionDiagnostic {
  topic: string;
  topic_type: string;
  status: string;
  publishers: string[];
  subscribers: string[];
  rate_hz?: number | null;
  qos_status: string;
  qos_mismatch_reason?: string | null;
}

export interface RuntimeVerificationResult {
  verified: boolean;
  contract_evaluated: boolean;
  status: 'RUNTIME_VERIFIED' | 'RUNTIME_FAILED' | 'RUNTIME_NOT_EXECUTED' | 'NO_CONTRACT_SPECIFIED';
  missing_nodes: string[];
  missing_topics: string[];
  type_mismatches: any[];
  qos_incompatibilities: any[];
  tf_warnings: string[];
  details: string;
}

export interface RuntimeSession {
  id: string;
  stack_id: string;
  workspace_digest: string;
  provider: string;
  ros_distro?: string | null;
  ros_domain_id?: number | null;
  status: 'PENDING' | 'RUNNING' | 'STOPPED' | 'FAILED';
  started_at: string;
  stopped_at?: string | null;
  build_verification_id?: string | null;
  simulation_adapter?: string | null;
}

export type ProviderInfo = ExecutionProviderInfo;
