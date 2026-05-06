export default function StatusPage() {
  return (
    <pre>
      {JSON.stringify(
        {
          status: "ok",
          service: "frontend",
          version: "0.1.0",
        },
        null,
        2
      )}
    </pre>
  );
}
