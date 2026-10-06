/** Frontend chat domain types — decoupled from backend response shapes. */

export type ChatMessageRole = "user" | "assistant" | "system";

export type AgentExecutionStatus =
  | "queued"
  | "in_progress"
  | "awaiting_approval"
  | "blocked"
  | "completed"
  | "failed"
  | "rejected"
  | "cancelled"
  | "unknown";

export type AttachmentStatus = "uploading" | "processing" | "ready" | "failed";

export type ChatAttachment = {
  id: string;
  filename: string;
  fileType: string | null;
  contentType: string | null;
  status: AttachmentStatus;
};

export type EngineeringArtifact = {
  id: string;
  name: string;
  artifactType: string;
  description: string | null;
  href: string | null;
};

export type EngineeringResultField = {
  label: string;
  value: string;
  unit: string | null;
};

export type DemoRcBeamInputs = {
  spanM: number | null;
  uniformLoadKnM: number | null;
  widthMm: number | null;
  heightMm: number | null;
  effectiveDepthMm: number | null;
  fcMpa: number | null;
  fyMpa: number | null;
};

export type DemoRcBeamNumericResults = {
  maxMomentKnM: number | null;
  maxShearKn: number | null;
};

export type DemoEngineeringResults = {
  kind: string;
  status: string;
  demo: boolean;
  disclaimer: string | null;
  code: string | null;
  fields: EngineeringResultField[];
  assumptions: string[];
  warnings: string[];
  inputs: DemoRcBeamInputs | null;
  numericResults: DemoRcBeamNumericResults | null;
};

export type AciRcBeamInputs = DemoRcBeamInputs & {
  asMm2: number | null;
};

export type AciRcBeamNumericResults = {
  muKnM: number | null;
  vuKn: number | null;
  phiMnKnM: number | null;
  phiVcKn: number | null;
  flexureUtilization: number | null;
  shearUtilization: number | null;
  governingUtilization: number | null;
  flexureOutcome: string | null;
  shearOutcome: string | null;
};

export type AciRcBeamResults = {
  kind: "aci_rc_beam";
  status: string;
  demo: boolean;
  disclaimer: string | null;
  code: string | null;
  pluginId: string | null;
  demandSource: string | null;
  inputUnits: string | null;
  internalUnits: string | null;
  outputUnits: string | null;
  fields: EngineeringResultField[];
  assumptions: string[];
  warnings: string[];
  missing: string[];
  inputs: AciRcBeamInputs | null;
  numericResults: AciRcBeamNumericResults | null;
};

export type AgentChatMode = "auto" | "analyze" | "design" | "cad" | "documents" | "reports";

export const AGENT_CHAT_MODES: ReadonlyArray<{ value: AgentChatMode; label: string }> = [
  { value: "auto", label: "Auto" },
  { value: "analyze", label: "Analyze" },
  { value: "design", label: "Design" },
  { value: "cad", label: "CAD" },
  { value: "documents", label: "Documents" },
  { value: "reports", label: "Reports" },
];

export type AgentRunStepState = "complete" | "current" | "pending" | "error";

export type AgentRunStep = {
  key: string;
  label: string;
  state: AgentRunStepState;
};

export type AgentToolDetail = {
  key?: string;
  label: string;
  state: AgentRunStepState;
};

export type AgentToolFile = {
  filename: string;
  fileType: string | null;
  availability: string | null;
  pageCount: number | null;
};

export type AgentToolArtifactRef = {
  id: string;
  name: string;
  artifactType: string;
};

export type AgentToolAction = {
  label: string;
  href: string;
};

export type AgentRunError = {
  title: string;
  reason: string;
};

export type AgentToolExecution = {
  id: string;
  name: string;
  capability: string | null;
  status: AgentRunStepState;
  operation?: string | null;
  operations?: string[];
  details: AgentToolDetail[];
  files?: AgentToolFile[];
  artifacts?: AgentToolArtifactRef[];
  counts?: Record<string, number>;
  actions?: AgentToolAction[];
  error?: AgentRunError | null;
};

export type AgentRunContext = {
  conversation: boolean;
  project: boolean;
  projectId: string | null;
  conversationId: string | null;
  capability: string | null;
  files: Array<{ filename: string; fileType: string | null; availability: string | null }>;
  indexedDocumentCount: number;
};

export type AgentRun = {
  lifecycle: string;
  currentStep: string;
  progress: AgentExecutionStatus | null;
  selectedCapability: string | null;
  requiresApproval: boolean;
  steps: AgentRunStep[];
  tools: AgentToolExecution[];
  context: AgentRunContext;
  validationStatus: string | null;
  error: AgentRunError | null;
};

export type EngineeringResult = {
  executionStatus: AgentExecutionStatus | null;
  selectedCapability: string | null;
  requiresApproval: boolean;
  approvalRequestId: string | null;
  statusEvents: string[];
  artifacts: EngineeringArtifact[];
  actions: Array<{ label: string; href: string }>;
  demoResults: DemoEngineeringResults | null;
  aciBeamResults: AciRcBeamResults | null;
  agentRun: AgentRun | null;
};

export type ChatMessage = {
  id: string;
  conversationId: string;
  role: ChatMessageRole;
  content: string;
  timestamp: string;
  attachments: ChatAttachment[];
  status: AgentExecutionStatus | null;
  engineeringResult: EngineeringResult | null;
};

export type Conversation = {
  id: string;
  title: string;
  projectId: string | null;
  updatedAt: string;
};

export type ExecutionPhase =
  | "idle"
  | "uploading"
  | "building_context"
  | "processing"
  | "error";

export type StreamingCapabilities = {
  supported: true;
  transport: "sse";
};

export const STREAMING_CAPABILITIES: StreamingCapabilities = {
  supported: true,
  transport: "sse",
};

export const ENGINEERING_FILE_ACCEPT =
  ".txt,.pdf,.dwg,.dxf,.edb,.sdb,.f2k,.xlsx,.xls,.docx,.doc,.csv,.png,.jpg,.jpeg,.gif,.webp";

export const ENGINEERING_PROMPT_EXAMPLES = [
  "Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m.",
  "Check this RC beam per ACI 318: span 6 m, 20 kN/m, b=300 mm, h=500 mm, d=450 mm, fc=25 MPa, fy=400 MPa, As=1500 mm2.",
  "Review this structural model and identify potential design issues.",
  "Calculate the required reinforcement for this column.",
  "Review the attached engineering document and summarize the governing structural requirements.",
  "زمین ۱۲×۲۲ متر، بر ۱۲ متر، پیلوت با ۴ پارکینگ، ۳ طبقه مسکونی، هر طبقه یک واحد، هر واحد ۳ خوابه",
] as const;
