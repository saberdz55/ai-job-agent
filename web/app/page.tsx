export default function Home() {
  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 32 }}>
      <p style={{ opacity: 0.7, marginBottom: 8 }}>AI JOB AGENT · CONTROL PLANE</p>
      <h1 style={{ fontSize: 42, margin: "0 0 12px" }}>Durable job application workflows</h1>
      <p style={{ maxWidth: 700, lineHeight: 1.6, opacity: 0.8 }}>
        Vercel orchestrates durable jobs. The desktop worker owns the real browser session. ChatGPT/MCP will control the workflow through authenticated tools.
      </p>
      <div style={{ marginTop: 28, padding: 20, border: "1px solid #2a2f38", borderRadius: 14 }}>
        <strong>Control plane status</strong>
        <p style={{ marginBottom: 0, opacity: 0.75 }}>Workflow runtime configured. Worker and MCP credentials are server-side only.</p>
      </div>
    </main>
  );
}
