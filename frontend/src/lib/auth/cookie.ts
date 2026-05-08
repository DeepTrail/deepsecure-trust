import { EncryptJWT, jwtDecrypt } from "jose";

const ALGORITHM = "A256GCM";
const ENCRYPTION = "dir";

function getEncryptionSecret(): Uint8Array {
  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    throw new Error(
      "SESSION_SECRET environment variable is required. " +
        "Run 'scripts/generate-env.sh' to create .env.local"
    );
  }
  const hex = secret.slice(0, 64);
  const bytes = new Uint8Array(32);
  for (let i = 0; i < 32; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

export async function encryptSession(jwt: string): Promise<string> {
  const secret = getEncryptionSecret();
  return new EncryptJWT({ jwt })
    .setProtectedHeader({ alg: ENCRYPTION, enc: ALGORITHM })
    .setIssuedAt()
    .setExpirationTime("8h")
    .encrypt(secret);
}

export async function decryptSession(
  cookie: string
): Promise<string | null> {
  try {
    const secret = getEncryptionSecret();
    const { payload } = await jwtDecrypt(cookie, secret);
    return (payload.jwt as string) ?? null;
  } catch {
    return null;
  }
}
