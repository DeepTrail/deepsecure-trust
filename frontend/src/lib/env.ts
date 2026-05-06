function requiredServerEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(
      `Missing required environment variable: ${key}. ` +
        `Run 'scripts/generate-env.sh' to create .env.local`
    );
  }
  return value;
}

function optionalEnv(key: string, defaultValue: string): string {
  return process.env[key] || defaultValue;
}

export const env = {
  DEEPTRAIL_CONTROL_INTERNAL_URL: requiredServerEnv(
    "DEEPTRAIL_CONTROL_INTERNAL_URL"
  ),
  DEEPTRAIL_GATEWAY_INTERNAL_URL: requiredServerEnv(
    "DEEPTRAIL_GATEWAY_INTERNAL_URL"
  ),
  SESSION_SECRET: requiredServerEnv("SESSION_SECRET"),
  CSRF_SECRET: requiredServerEnv("CSRF_SECRET"),

  NEXT_PUBLIC_APP_NAME: optionalEnv("NEXT_PUBLIC_APP_NAME", "DeepSecure"),
  NEXT_PUBLIC_DEMO_ENABLED: optionalEnv("NEXT_PUBLIC_DEMO_ENABLED", "true"),
  NEXT_PUBLIC_IDP_DEFAULT: optionalEnv("NEXT_PUBLIC_IDP_DEFAULT", "keycloak"),
} as const;
