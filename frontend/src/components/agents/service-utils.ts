const SERVICE_DISPLAY_NAMES: Record<string, string> = {
  notion: "Notion",
  slack: "Slack",
  github: "GitHub",
  gcalendar: "Google Calendar",
  gdrive: "Google Drive",
  gmail: "Gmail",
  hubspot: "HubSpot",
  jira: "Jira",
  confluence: "Confluence",
  salesforce: "Salesforce",
  linear: "Linear",
  asana: "Asana",
  figma: "Figma",
  dropbox: "Dropbox",
};

export function getServiceDisplayName(serviceId: string): string {
  return SERVICE_DISPLAY_NAMES[serviceId] ?? serviceId.charAt(0).toUpperCase() + serviceId.slice(1);
}

const STATUS_COLORS: Record<string, string> = {
  connected: "text-green-600 border-green-200 bg-green-50",
  token_expired: "text-amber-600 border-amber-200 bg-amber-50",
  not_connected: "text-gray-400 border-gray-200 bg-gray-50",
};

export function getServiceStatusColor(status: string): string {
  return STATUS_COLORS[status] ?? STATUS_COLORS.not_connected;
}

export function groupPermissionsByService(permissions: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const perm of permissions) {
    const service = perm.includes(":") ? perm.split(":")[0] : "other";
    if (!groups[service]) groups[service] = [];
    groups[service].push(perm);
  }
  return groups;
}

export function extractServiceIds(permissions: string[]): string[] {
  const ids = new Set<string>();
  for (const perm of permissions) {
    if (perm.includes(":")) ids.add(perm.split(":")[0]);
  }
  return Array.from(ids).sort();
}
