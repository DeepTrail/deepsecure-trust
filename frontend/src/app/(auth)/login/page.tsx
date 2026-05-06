import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const SSO_PROVIDERS = [
  { id: "keycloak", label: "Sign in with Keycloak" },
  { id: "google", label: "Sign in with Google" },
] as const;

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Sign in to DeepSecure</CardTitle>
          <CardDescription>
            Choose your identity provider to continue
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {SSO_PROVIDERS.map((provider) => (
            <Button
              key={provider.id}
              variant="outline"
              className="w-full"
              asChild
            >
              <Link href={`/api/auth/sso/${provider.id}`}>
                {provider.label}
              </Link>
            </Button>
          ))}
          <Separator />
          <p className="text-center text-xs text-muted-foreground">
            By signing in, you agree to the DeepSecure Terms of Service.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
