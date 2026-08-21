import { start } from "workflow/api";
import { NextResponse } from "next/server";
import { runJobApplication, type JobApplicationInput } from "@/workflows/job-application";

function unauthorized() {
  return NextResponse.json({ error: "unauthorized" }, { status: 401 });
}

export async function POST(request: Request) {
  const expected = process.env.CONTROL_PLANE_TOKEN;
  const supplied = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "");

  if (!expected || !supplied || supplied !== expected) {
    return unauthorized();
  }

  const body = (await request.json()) as Partial<JobApplicationInput>;

  if (!body.jobId || !body.applicationUrl || !body.idempotencyKey) {
    return NextResponse.json({ error: "jobId, applicationUrl and idempotencyKey are required" }, { status: 400 });
  }

  const input: JobApplicationInput = {
    jobId: body.jobId,
    applicationUrl: body.applicationUrl,
    idempotencyKey: body.idempotencyKey,
    mode: body.mode === "auto_apply" ? "auto_apply" : "prepare",
  };

  const run = await start(runJobApplication, [input]);

  return NextResponse.json({
    runId: run.runId,
    jobId: input.jobId,
    status: "queued",
  }, { status: 202 });
}
