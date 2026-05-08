export default function DemoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="demo-console min-h-screen bg-background">
      {children}
    </div>
  );
}
