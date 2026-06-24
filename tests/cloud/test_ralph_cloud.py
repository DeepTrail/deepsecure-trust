"""Tests for AFK cloud execution: Dockerfiles, cloud entry, deploy scripts, manifests."""

import json
import os
import subprocess

import pytest
import yaml


SANDBOX_DOCKERFILE = "Dockerfile.afk-sandbox"
CLOUD_DOCKERFILE = "Dockerfile.afk-cloud"
CLOUD_ENTRY = "scripts/ralph-cloud-entry.sh"
DEPLOY_SCRIPT = "scripts/deploy-afk-cloud.sh"
GCP_MANIFEST = "infra/afk-cloud-run-job.yaml"
AWS_TASK_DEF = "infra/afk-ecs-task.json"
PARALLEL_WORKFLOW = ".claude/workflows/parallel-batch.js"
ADVERSARIAL_WORKFLOW = ".claude/workflows/adversarial-review.js"


class TestDockerfiles:
    def test_sandbox_dockerfile_exists(self):
        assert os.path.isfile(SANDBOX_DOCKERFILE)

    def test_cloud_dockerfile_exists(self):
        assert os.path.isfile(CLOUD_DOCKERFILE)

    def test_sandbox_dockerfile_has_network_none_comment(self):
        with open(SANDBOX_DOCKERFILE) as f:
            content = f.read()
        assert "--network none" in content

    def test_sandbox_uses_nonroot_user(self):
        with open(SANDBOX_DOCKERFILE) as f:
            content = f.read()
        assert "USER afk-agent" in content

    def test_cloud_uses_nonroot_user(self):
        with open(CLOUD_DOCKERFILE) as f:
            content = f.read()
        assert "USER afk-agent" in content

    def test_sandbox_copies_ralph(self):
        with open(SANDBOX_DOCKERFILE) as f:
            content = f.read()
        assert "ralph.sh" in content

    def test_cloud_copies_entry_script(self):
        with open(CLOUD_DOCKERFILE) as f:
            content = f.read()
        assert "ralph-cloud-entry.sh" in content

    def test_sandbox_installs_claude_code(self):
        with open(SANDBOX_DOCKERFILE) as f:
            content = f.read()
        assert "claude-code" in content

    def test_cloud_installs_claude_code(self):
        with open(CLOUD_DOCKERFILE) as f:
            content = f.read()
        assert "claude-code" in content

    def test_sandbox_has_healthcheck(self):
        with open(SANDBOX_DOCKERFILE) as f:
            content = f.read()
        assert "HEALTHCHECK" in content

    def test_sandbox_entrypoint_is_ralph(self):
        with open(SANDBOX_DOCKERFILE) as f:
            content = f.read()
        assert "ralph.sh" in content
        assert "ENTRYPOINT" in content


class TestCloudEntryScript:
    def test_script_exists(self):
        assert os.path.isfile(CLOUD_ENTRY)

    def test_script_executable(self):
        assert os.access(CLOUD_ENTRY, os.X_OK)

    def test_requires_repo_url(self):
        result = subprocess.run(
            ["bash", "-c", f"AFK_BRANCH=x AFK_WORKSTREAM=x ANTHROPIC_API_KEY=x bash {CLOUD_ENTRY}"],
            capture_output=True,
            text=True,
            env={**os.environ, "AFK_REPO_URL": "", "AFK_BRANCH": "x", "AFK_WORKSTREAM": "x", "ANTHROPIC_API_KEY": "x"},
        )
        assert result.returncode != 0

    def test_requires_branch(self):
        result = subprocess.run(
            ["bash", "-c", f"AFK_REPO_URL=x AFK_WORKSTREAM=x ANTHROPIC_API_KEY=x bash {CLOUD_ENTRY}"],
            capture_output=True,
            text=True,
            env={**os.environ, "AFK_REPO_URL": "x", "AFK_BRANCH": "", "AFK_WORKSTREAM": "x", "ANTHROPIC_API_KEY": "x"},
        )
        assert result.returncode != 0

    def test_requires_workstream(self):
        result = subprocess.run(
            ["bash", "-c", f"AFK_REPO_URL=x AFK_BRANCH=x ANTHROPIC_API_KEY=x bash {CLOUD_ENTRY}"],
            capture_output=True,
            text=True,
            env={**os.environ, "AFK_REPO_URL": "x", "AFK_BRANCH": "x", "AFK_WORKSTREAM": "", "ANTHROPIC_API_KEY": "x"},
        )
        assert result.returncode != 0

    def test_requires_api_key(self):
        result = subprocess.run(
            ["bash", "-c", f"AFK_REPO_URL=x AFK_BRANCH=x AFK_WORKSTREAM=x bash {CLOUD_ENTRY}"],
            capture_output=True,
            text=True,
            env={**os.environ, "AFK_REPO_URL": "x", "AFK_BRANCH": "x", "AFK_WORKSTREAM": "x", "ANTHROPIC_API_KEY": ""},
        )
        assert result.returncode != 0

    def test_auto_detects_gcp(self):
        with open(CLOUD_ENTRY) as f:
            content = f.read()
        assert "K_SERVICE" in content
        assert "gcp-cloud-run" in content

    def test_auto_detects_aws(self):
        with open(CLOUD_ENTRY) as f:
            content = f.read()
        assert "ECS_CONTAINER_METADATA_URI" in content
        assert "aws-ecs" in content


class TestDeployScript:
    def test_script_exists(self):
        assert os.path.isfile(DEPLOY_SCRIPT)

    def test_script_executable(self):
        assert os.access(DEPLOY_SCRIPT, os.X_OK)

    def test_requires_platform_arg(self):
        result = subprocess.run(
            ["bash", DEPLOY_SCRIPT],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_dry_run_gcp(self):
        result = subprocess.run(
            ["bash", DEPLOY_SCRIPT, "build", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "DRY RUN" in result.stdout

    def test_supports_gcp_platform(self):
        with open(DEPLOY_SCRIPT) as f:
            content = f.read()
        assert "deploy_gcp" in content

    def test_supports_aws_platform(self):
        with open(DEPLOY_SCRIPT) as f:
            content = f.read()
        assert "deploy_aws" in content


class TestGCPManifest:
    def test_manifest_exists(self):
        assert os.path.isfile(GCP_MANIFEST)

    def test_manifest_valid_yaml(self):
        with open(GCP_MANIFEST) as f:
            config = yaml.safe_load(f)
        assert config is not None

    def test_manifest_has_job_kind(self):
        with open(GCP_MANIFEST) as f:
            config = yaml.safe_load(f)
        assert config["kind"] == "Job"

    def test_manifest_has_env_vars(self):
        with open(GCP_MANIFEST) as f:
            config = yaml.safe_load(f)
        container = config["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
        env_names = [e["name"] for e in container["env"]]
        assert "AFK_REPO_URL" in env_names
        assert "AFK_BRANCH" in env_names
        assert "AFK_WORKSTREAM" in env_names
        assert "ANTHROPIC_API_KEY" in env_names

    def test_manifest_has_resource_limits(self):
        with open(GCP_MANIFEST) as f:
            config = yaml.safe_load(f)
        container = config["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
        assert "memory" in container["resources"]["limits"]
        assert "cpu" in container["resources"]["limits"]

    def test_manifest_has_timeout(self):
        with open(GCP_MANIFEST) as f:
            config = yaml.safe_load(f)
        timeout = config["spec"]["template"]["spec"]["template"]["spec"]["timeoutSeconds"]
        assert timeout >= 3600

    def test_manifest_no_restart(self):
        with open(GCP_MANIFEST) as f:
            config = yaml.safe_load(f)
        restart = config["spec"]["template"]["spec"]["template"]["spec"]["restartPolicy"]
        assert restart == "Never"


class TestAWSTaskDef:
    def test_task_def_exists(self):
        assert os.path.isfile(AWS_TASK_DEF)

    def test_task_def_valid_json(self):
        with open(AWS_TASK_DEF) as f:
            config = json.load(f)
        assert config is not None

    def test_task_def_fargate(self):
        with open(AWS_TASK_DEF) as f:
            config = json.load(f)
        assert "FARGATE" in config["requiresCompatibilities"]

    def test_task_def_has_env_vars(self):
        with open(AWS_TASK_DEF) as f:
            config = json.load(f)
        container = config["containerDefinitions"][0]
        env_names = [e["name"] for e in container["environment"]]
        assert "AFK_REPO_URL" in env_names
        assert "AFK_BRANCH" in env_names
        assert "AFK_WORKSTREAM" in env_names

    def test_task_def_has_secrets(self):
        with open(AWS_TASK_DEF) as f:
            config = json.load(f)
        container = config["containerDefinitions"][0]
        secret_names = [s["name"] for s in container["secrets"]]
        assert "ANTHROPIC_API_KEY" in secret_names

    def test_task_def_has_logging(self):
        with open(AWS_TASK_DEF) as f:
            config = json.load(f)
        container = config["containerDefinitions"][0]
        assert container["logConfiguration"]["logDriver"] == "awslogs"

    def test_task_def_resource_limits(self):
        with open(AWS_TASK_DEF) as f:
            config = json.load(f)
        assert int(config["cpu"]) >= 1024
        assert int(config["memory"]) >= 2048


class TestDynamicWorkflows:
    def test_parallel_batch_exists(self):
        assert os.path.isfile(PARALLEL_WORKFLOW)

    def test_adversarial_review_exists(self):
        assert os.path.isfile(ADVERSARIAL_WORKFLOW)

    def test_parallel_batch_exports_run(self):
        with open(PARALLEL_WORKFLOW) as f:
            content = f.read()
        assert "module.exports" in content
        assert "run" in content

    def test_adversarial_review_exports_run(self):
        with open(ADVERSARIAL_WORKFLOW) as f:
            content = f.read()
        assert "module.exports" in content
        assert "run" in content

    def test_parallel_batch_uses_worktree_isolation(self):
        with open(PARALLEL_WORKFLOW) as f:
            content = f.read()
        assert "worktree" in content

    def test_adversarial_review_uses_verifier_agent(self):
        with open(ADVERSARIAL_WORKFLOW) as f:
            content = f.read()
        assert "afk-verifier" in content

    def test_parallel_batch_handles_errors(self):
        with open(PARALLEL_WORKFLOW) as f:
            content = f.read()
        assert "catch" in content
        assert "failed" in content

    def test_adversarial_review_has_severity_levels(self):
        with open(ADVERSARIAL_WORKFLOW) as f:
            content = f.read()
        assert "critical" in content
        assert "major" in content
        assert "minor" in content


class TestNotifyCloudDetection:
    def test_notify_has_cloud_env_handling(self):
        with open("scripts/notify.sh") as f:
            content = f.read()
        assert "AFK_CLOUD_ENV" in content

    def test_notify_structured_logging_in_cloud(self):
        with open("scripts/notify.sh") as f:
            content = f.read()
        assert "severity" in content
        assert "json" in content.lower()

    def test_notify_skips_macos_in_cloud(self):
        with open("scripts/notify.sh") as f:
            content = f.read()
        assert 'if [ -z "$CLOUD_ENV" ]' in content

    def test_notify_cloud_env_detection(self):
        result = subprocess.run(
            ["bash", "scripts/notify.sh", "Test", "Cloud test", "info"],
            capture_output=True,
            text=True,
            env={**os.environ, "AFK_CLOUD_ENV": "test-cloud"},
        )
        assert result.returncode == 0
