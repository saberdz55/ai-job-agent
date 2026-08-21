import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({
    ok: true,
    service: "ai-job-agent-control-plane",
    version: "v1",
    workflow: "enabled",
  });
}
