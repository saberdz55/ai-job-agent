export type JobApplicationInput = {
  jobId: string;
  applicationUrl: string;
  mode: "prepare" | "auto_apply";
  idempotencyKey: string;
};

export type JobApplicationResult = {
  jobId: string;
  status: string;
  workflowVersion: string;
};

async function dispatchBrowserWorker(input: JobApplicationInput): Promise<{ status: string; jobId: string }> {
  "use step";

  const workerUrl = process.env.BROWSER_WORKER_URL;
  const workerToken = process.env.BROWSER_WORKER_TOKEN;

  if (!workerUrl || !workerToken) {
    throw new Error("Browser worker is not configured");
  }

  const response = await fetch(`${workerUrl.replace(/\/$/, "")}/v1/applications/execute`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${workerToken}`,
      "x-idempotency-key": input.idempotencyKey,
    },
    body: JSON.stringify(input),
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Browser worker returned ${response.status}: ${text.slice(0, 500)}`);
  }

  return (await response.json()) as { status: string; jobId: string };
}

export async function runJobApplication(input: JobApplicationInput): Promise<JobApplicationResult> {
  "use workflow";

  const result = await dispatchBrowserWorker(input);

  return {
    jobId: result.jobId,
    status: result.status,
    workflowVersion: "v1",
  };
}
