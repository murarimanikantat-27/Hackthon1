"""
Remediation Rules — pre-approved actions mapped to incident types.
Controls what the agent is allowed to auto-remediate vs. flag for manual review.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RemediationRule:
    """Defines a remediation action for a specific incident pattern."""
    name: str
    description: str
    pattern: str  # what to match in the incident (e.g. "CrashLoopBackOff")
    auto_approve: bool  # whether the agent can auto-execute this
    kubectl_command_template: str  # template with {namespace}, {pod_name}, {deployment_name}
    risk_level: str  # low, medium, high
    cooldown_minutes: int = 10  # don't re-execute within this window


# ─── Pre-Approved Remediation Rules ───

REMEDIATION_RULES: List[RemediationRule] = [

    # ═══════════════════════════════════════════════
    # Pod & Container Errors
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="restart_crashed_pod",
        description="Delete and let the controller recreate a CrashLoopBackOff pod",
        pattern="CrashLoopBackOff",
        auto_approve=True,
        kubectl_command_template="delete pod {pod_name} -n {namespace}",
        risk_level="low",
        cooldown_minutes=5,
    ),
    RemediationRule(
        name="restart_error_pod",
        description="Delete pod in Error or unexpected Completed state",
        pattern="Error",
        auto_approve=True,
        kubectl_command_template="delete pod {pod_name} -n {namespace}",
        risk_level="low",
        cooldown_minutes=5,
    ),
    RemediationRule(
        name="oom_killed_increase_memory",
        description="OOMKilled — pod killed due to out of memory. Suggest increasing memory limits.",
        pattern="OOMKilled",
        auto_approve=False,
        kubectl_command_template="set resources deployment/{deployment_name} -n {namespace} --limits=memory=512Mi",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="container_cannot_run",
        description="ContainerCannotRun — container runtime failure. Restart the pod.",
        pattern="ContainerCannotRun",
        auto_approve=True,
        kubectl_command_template="delete pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=10,
    ),
    RemediationRule(
        name="create_container_config_error",
        description="CreateContainerConfigError — missing ConfigMap, Secret, or env var reference.",
        pattern="CreateContainerConfigError",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="create_container_error",
        description="CreateContainerError — container creation failed at runtime level.",
        pattern="CreateContainerError",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="run_container_error",
        description="RunContainerError — container failed to start (bad entrypoint/command).",
        pattern="RunContainerError",
        auto_approve=False,
        kubectl_command_template="logs {pod_name} -n {namespace} --previous",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="container_creating_stuck",
        description="ContainerCreating stuck — pod stuck creating container, usually volume or image issue.",
        pattern="ContainerCreating",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=15,
    ),

    # ═══════════════════════════════════════════════
    # Image & Registry Errors
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="err_image_pull",
        description="ErrImagePull — failed to pull container image. Check image name, tag, and registry access.",
        pattern="ErrImagePull",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="image_pull_backoff",
        description="ImagePullBackOff — repeated image pull failures with backoff.",
        pattern="ImagePullBackOff",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="invalid_image_name",
        description="InvalidImageName — container image name is malformed.",
        pattern="InvalidImageName",
        auto_approve=False,
        kubectl_command_template="get pod {pod_name} -n {namespace} -o jsonpath='{.spec.containers[*].image}'",
        risk_level="medium",
        cooldown_minutes=30,
    ),

    # ═══════════════════════════════════════════════
    # Scheduling Errors
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="pending_pod",
        description="Pending — pod cannot be scheduled. Check resource requests, node capacity, and taints.",
        pattern="Pending",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="unschedulable",
        description="Unschedulable — no nodes available for scheduling.",
        pattern="Unschedulable",
        auto_approve=False,
        kubectl_command_template="get nodes -o wide",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="insufficient_cpu",
        description="Insufficient CPU — cluster lacks CPU resources for the pod.",
        pattern="Insufficient cpu",
        auto_approve=False,
        kubectl_command_template="top nodes",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="insufficient_memory",
        description="Insufficient Memory — cluster lacks memory resources for the pod.",
        pattern="Insufficient memory",
        auto_approve=False,
        kubectl_command_template="top nodes",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="node_not_ready_scheduling",
        description="Node not ready — pods can't be scheduled on unhealthy nodes.",
        pattern="NodeNotReady",
        auto_approve=False,
        kubectl_command_template="describe node {node_name}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="taint_toleration_mismatch",
        description="Taint/Toleration mismatch — pod doesn't tolerate node taints.",
        pattern="didn't match pod's node affinity",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="failed_scheduling",
        description="FailedScheduling — scheduler could not place the pod on any node.",
        pattern="FailedScheduling",
        auto_approve=False,
        kubectl_command_template="get events --field-selector reason=FailedScheduling -n {namespace}",
        risk_level="high",
        cooldown_minutes=15,
    ),

    # ═══════════════════════════════════════════════
    # Configuration Errors
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="configmap_not_found",
        description="ConfigMap not found — pod refers to a missing ConfigMap.",
        pattern="configmaps",
        auto_approve=False,
        kubectl_command_template="get configmaps -n {namespace}",
        risk_level="medium",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="secret_not_found",
        description="Secret not found — pod refers to a missing Secret.",
        pattern="secrets",
        auto_approve=False,
        kubectl_command_template="get secrets -n {namespace}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="volume_mount_failure",
        description="Volume mount failure — PVC or volume could not be mounted.",
        pattern="MountVolume",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="pvc_pending",
        description="PVC Pending / Not Bound — PersistentVolumeClaim is not bound to a volume.",
        pattern="PVC",
        auto_approve=False,
        kubectl_command_template="get pvc -n {namespace}",
        risk_level="high",
        cooldown_minutes=30,
    ),

    # ═══════════════════════════════════════════════
    # Health & Probe Errors
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="liveness_probe_failed",
        description="Liveness probe failed — Kubernetes will restart the container.",
        pattern="Liveness probe failed",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=10,
    ),
    RemediationRule(
        name="readiness_probe_failed",
        description="Readiness probe failed — pod removed from service endpoints.",
        pattern="Readiness probe failed",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=10,
    ),
    RemediationRule(
        name="startup_probe_failed",
        description="Startup probe failed — container failed to start within the deadline.",
        pattern="Startup probe failed",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=10,
    ),
    RemediationRule(
        name="backoff_restart_failed",
        description="Back-off restarting failed container — repeated restart failures.",
        pattern="Back-off restarting failed container",
        auto_approve=True,
        kubectl_command_template="delete pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=10,
    ),

    # ═══════════════════════════════════════════════
    # Node & Cluster Errors
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="node_not_ready",
        description="Node NotReady — node is unhealthy and cannot run workloads.",
        pattern="NotReady",
        auto_approve=False,
        kubectl_command_template="describe node {node_name}",
        risk_level="critical",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="disk_pressure",
        description="DiskPressure — node is running low on disk space.",
        pattern="DiskPressure",
        auto_approve=False,
        kubectl_command_template="describe node {node_name}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="memory_pressure",
        description="MemoryPressure — node is running low on memory.",
        pattern="MemoryPressure",
        auto_approve=False,
        kubectl_command_template="describe node {node_name}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="pid_pressure",
        description="PIDPressure — node is running too many processes.",
        pattern="PIDPressure",
        auto_approve=False,
        kubectl_command_template="describe node {node_name}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="network_unavailable",
        description="NetworkUnavailable — node network is not configured correctly.",
        pattern="NetworkUnavailable",
        auto_approve=False,
        kubectl_command_template="describe node {node_name}",
        risk_level="critical",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="evicted_pod_cleanup",
        description="Clean up evicted pods in a namespace.",
        pattern="Evicted",
        auto_approve=True,
        kubectl_command_template="delete pods --field-selector=status.phase==Failed -n {namespace}",
        risk_level="low",
        cooldown_minutes=10,
    ),

    # ═══════════════════════════════════════════════
    # Controller & Deployment Errors
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="rollout_restart_deployment",
        description="Rollout restart a deployment with high restart count.",
        pattern="HighRestartCount",
        auto_approve=True,
        kubectl_command_template="rollout restart deployment/{deployment_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="replicaset_mismatch",
        description="ReplicaSet mismatch — desired vs actual replicas differ.",
        pattern="ReplicaSet",
        auto_approve=False,
        kubectl_command_template="describe deployment {deployment_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="progress_deadline_exceeded",
        description="ProgressDeadlineExceeded — deployment rollout is stuck.",
        pattern="ProgressDeadlineExceeded",
        auto_approve=False,
        kubectl_command_template="rollout status deployment/{deployment_name} -n {namespace}",
        risk_level="high",
        cooldown_minutes=30,
    ),
    RemediationRule(
        name="failed_create",
        description="FailedCreate — controller failed to create pods.",
        pattern="FailedCreate",
        auto_approve=False,
        kubectl_command_template="get events --field-selector reason=FailedCreate -n {namespace}",
        risk_level="high",
        cooldown_minutes=15,
    ),

    # ═══════════════════════════════════════════════
    # Prometheus / Control Plane Alerts
    # ═══════════════════════════════════════════════
    RemediationRule(
        name="kube_controller_manager_down",
        description="KubeControllerManagerDown — controller-manager target disappeared from Prometheus.",
        pattern="KubeControllerManagerDown",
        auto_approve=False,
        kubectl_command_template="get pods -n kube-system -l component=kube-controller-manager",
        risk_level="critical",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="kube_scheduler_down",
        description="KubeSchedulerDown — scheduler target disappeared from Prometheus.",
        pattern="KubeSchedulerDown",
        auto_approve=False,
        kubectl_command_template="get pods -n kube-system -l component=kube-scheduler",
        risk_level="critical",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="kube_proxy_down",
        description="KubeProxyDown — kube-proxy target disappeared from Prometheus.",
        pattern="KubeProxyDown",
        auto_approve=False,
        kubectl_command_template="get pods -n kube-system -l k8s-app=kube-proxy",
        risk_level="high",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="kubelet_down",
        description="KubeletDown — kubelet target disappeared from Prometheus.",
        pattern="KubeletDown",
        auto_approve=False,
        kubectl_command_template="get nodes -o wide",
        risk_level="critical",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="target_down",
        description="Target disappeared from Prometheus target discovery.",
        pattern="Target disappeared",
        auto_approve=False,
        kubectl_command_template="get pods -n {namespace} -o wide",
        risk_level="high",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="watchdog",
        description="Watchdog — AlertManager health check alert (always firing, normal).",
        pattern="Watchdog",
        auto_approve=False,
        kubectl_command_template="get pods -n monitoring",
        risk_level="low",
        cooldown_minutes=60,
    ),
    RemediationRule(
        name="kube_pod_crash_looping",
        description="KubePodCrashLooping — pod is restarting frequently (>0 restarts in 10m).",
        pattern="KubePodCrashLooping",
        auto_approve=True,
        kubectl_command_template="delete pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=10,
    ),
    RemediationRule(
        name="kube_pod_not_ready",
        description="KubePodNotReady — pod has been in not-ready state for too long.",
        pattern="KubePodNotReady",
        auto_approve=False,
        kubectl_command_template="describe pod {pod_name} -n {namespace}",
        risk_level="medium",
        cooldown_minutes=15,
    ),
    RemediationRule(
        name="kube_deployment_replica_mismatch",
        description="KubeDeploymentReplicasMismatch — deployment has not matched expected replicas.",
        pattern="KubeDeploymentReplicasMismatch",
        auto_approve=False,
        kubectl_command_template="describe deployment {deployment_name} -n {namespace}",
        risk_level="high",
        cooldown_minutes=15,
    ),
]


def find_matching_rule(incident_description: str, raw_data: str = "") -> Optional[RemediationRule]:
    """Find the first remediation rule that matches the incident."""
    search_text = f"{incident_description} {raw_data}".lower()
    for rule in REMEDIATION_RULES:
        if rule.pattern.lower() in search_text:
            return rule
    return None


def build_remediation_command(rule: RemediationRule, context: Dict[str, str]) -> str:
    """Build the actual kubectl command from a rule template and context."""
    if not rule.kubectl_command_template:
        return ""
    try:
        return rule.kubectl_command_template.format(**context)
    except KeyError as e:
        return f"# Missing context variable: {e}"


def get_all_rules() -> List[Dict]:
    """Return all rules as dictionaries (for API/dashboard)."""
    return [
        {
            "name": r.name,
            "description": r.description,
            "pattern": r.pattern,
            "auto_approve": r.auto_approve,
            "risk_level": r.risk_level,
            "cooldown_minutes": r.cooldown_minutes,
        }
        for r in REMEDIATION_RULES
    ]
