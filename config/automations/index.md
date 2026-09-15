# Automations

A job definition explains its purpose, schedule and timezone, owner host, runtime, inputs, outputs, state location, recovery procedure and verification receipt. One designated runner owns each recurring job.

- Native launch-agent definitions, when installed, remain in their existing host-specific location.
- [Workflow scripts](../scripts/index.md)
- [Signal definitions](../signals/index.md)
- [Existing state records](../state/)
- [Config](../index.md)

Installed cron/launchd and application schedules may live outside this folder. These references do not prove that a job is active. Keep actual job ownership and dated evidence authoritative. The ontology migration changes no schedules and activates no paused jobs.
