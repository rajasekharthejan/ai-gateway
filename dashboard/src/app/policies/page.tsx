"use client";

export default function PoliciesPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Policies</h1>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
          Access Control Policies
        </h2>
        <p className="text-gray-400 text-sm mb-4">
          Policies control which teams can access which models, with optional
          conditions like token limits, time windows, and model allowlists.
        </p>

        <div className="space-y-3">
          <div className="bg-gray-800/50 rounded-md p-4 text-sm">
            <h3 className="font-medium mb-1">Policy Types</h3>
            <ul className="text-gray-400 space-y-1 ml-4 list-disc">
              <li>
                <strong className="text-gray-300">Allow</strong> — Explicitly
                permit access to matched resources
              </li>
              <li>
                <strong className="text-gray-300">Deny</strong> — Block access
                to matched resources
              </li>
            </ul>
          </div>

          <div className="bg-gray-800/50 rounded-md p-4 text-sm">
            <h3 className="font-medium mb-1">Conditions</h3>
            <ul className="text-gray-400 space-y-1 ml-4 list-disc">
              <li>
                <code className="text-blue-400">max_tokens</code> — Deny if
                request exceeds N tokens
              </li>
              <li>
                <code className="text-blue-400">time_window</code> — Apply only
                during specific UTC hours
              </li>
              <li>
                <code className="text-blue-400">allowed_models</code> —
                Allowlist of model names
              </li>
              <li>
                <code className="text-blue-400">denied_models</code> — Blocklist
                of model names
              </li>
            </ul>
          </div>

          <div className="bg-gray-800/50 rounded-md p-4 text-sm font-mono text-gray-400">
            <p className="text-gray-500 mb-1"># Create policy via Admin API:</p>
            <p>
              curl -X POST /v1/policies \
            </p>
            <p className="pl-4">
              -H &quot;X-Admin-Key: $KEY&quot; \
            </p>
            <p className="pl-4">
              -d {"'{"}
              &quot;name&quot;: &quot;Block GPT-4 for interns&quot;,
            </p>
            <p className="pl-6">
              &quot;team_id&quot;: &quot;...&quot;,
            </p>
            <p className="pl-6">
              &quot;policy_type&quot;: &quot;deny&quot;,
            </p>
            <p className="pl-6">
              &quot;resource&quot;: &quot;gpt-4*&quot;{"}'"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
