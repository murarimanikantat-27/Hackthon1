"""
Example Python Flask API for Incident Management
This file shows the expected API structure for the IncidentModal component
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
from io import BytesIO

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Sample incident data
incidents_db = [
    {
        "id": 1,
        "title": "Pod CrashLoopBackOff in production namespace",
        "severity": "critical",
        "status": "detected",
        "namespace": "prod-api",
        "resource_type": "Pod",
        "resource_name": "api-server-7d9f8",
        "detected_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "rca": {
            "root_cause": "Memory limit exceeded causing OOMKilled",
            "confidence_score": 0.92,
            "analysis": "Container memory usage exceeded the configured limit of 512Mi, causing the pod to be killed by the OOM killer.",
            "recommendations": [
                "Increase memory limit to 1Gi",
                "Add memory request to ensure QoS",
                "Review application memory leaks"
            ]
        },
        "actions": [
            {
                "action_type": "Scale Resources",
                "status": "pending",
                "command": "kubectl set resources deployment api-server --limits=memory=1Gi"
            }
        ]
    },
    {
        "id": 2,
        "title": "High CPU usage detected on worker nodes",
        "severity": "high",
        "status": "analyzing",
        "namespace": "kube-system",
        "resource_type": "Node",
        "resource_name": "worker-node-3",
        "detected_at": (datetime.now() - timedelta(hours=2)).isoformat(),
        "rca": {
            "root_cause": "Excessive pod scheduling on single node",
            "confidence_score": 0.78,
            "analysis": "Node affinity rules causing uneven pod distribution across cluster nodes.",
            "recommendations": [
                "Review pod affinity/anti-affinity rules",
                "Enable pod topology spread constraints",
                "Consider adding more worker nodes"
            ]
        },
        "actions": []
    },
    {
        "id": 3,
        "title": "Service endpoint not available",
        "severity": "medium",
        "status": "validating",
        "namespace": "default",
        "resource_type": "Service",
        "resource_name": "frontend-svc",
        "detected_at": (datetime.now() - timedelta(hours=3)).isoformat(),
        "rca": {
            "root_cause": "No healthy backend pods available",
            "confidence_score": 0.85,
            "analysis": "All backend pods failed readiness probe due to database connection timeout.",
            "recommendations": [
                "Check database connectivity",
                "Review readiness probe configuration",
                "Verify network policies"
            ]
        },
        "actions": [
            {
                "action_type": "Restart Pods",
                "status": "success",
                "command": "kubectl rollout restart deployment frontend",
                "result": "Deployment restarted successfully"
            }
        ]
    },
    {
        "id": 4,
        "title": "Persistent volume claim pending",
        "severity": "medium",
        "status": "monitoring",
        "namespace": "data",
        "resource_type": "PVC",
        "resource_name": "postgres-data",
        "detected_at": (datetime.now() - timedelta(hours=4)).isoformat(),
        "rca": {
            "root_cause": "No storage class available matching requirements",
            "confidence_score": 0.65,
            "analysis": "Requested storage class 'fast-ssd' not found in cluster.",
            "recommendations": [
                "Create required storage class",
                "Use existing storage class",
                "Provision additional storage"
            ]
        },
        "actions": []
    },
    {
        "id": 5,
        "title": "Image pull error in staging",
        "severity": "low",
        "status": "resolved",
        "namespace": "staging",
        "resource_type": "Pod",
        "resource_name": "app-staging-abc123",
        "detected_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "rca": {
            "root_cause": "Invalid image registry credentials",
            "confidence_score": 0.95,
            "analysis": "ImagePullBackOff due to authentication failure with private registry.",
            "recommendations": [
                "Update image pull secret",
                "Verify registry credentials",
                "Check network connectivity to registry"
            ]
        },
        "actions": [
            {
                "action_type": "Update Secret",
                "status": "success",
                "command": "kubectl create secret docker-registry regcred --docker-server=registry.io",
                "result": "Secret updated successfully"
            }
        ]
    }
]


@app.route('/api/incidents/', methods=['GET'])
def get_incidents():
    """Get all incidents"""
    return jsonify(incidents_db), 200


@app.route('/api/incidents/<int:incident_id>', methods=['GET'])
def get_incident_details(incident_id):
    """Get details for a specific incident"""
    incident = next((inc for inc in incidents_db if inc['id'] == incident_id), None)
    if incident:
        return jsonify(incident), 200
    return jsonify({"error": "Incident not found"}), 404


@app.route('/api/incidents/<int:incident_id>/remediate', methods=['POST'])
def remediate_incident(incident_id):
    """
    Trigger remediation for a specific incident
    This endpoint approves and executes the remediation actions
    """
    incident = next((inc for inc in incidents_db if inc['id'] == incident_id), None)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    
    # Check if there are actions to execute
    if not incident.get('actions') or len(incident['actions']) == 0:
        return jsonify({"error": "No remediation actions available for this incident"}), 400
    
    # Update action statuses
    executed_actions = []
    if incident['actions']:
        for action in incident['actions']:
            if action['status'] == 'pending':
                action['status'] = 'in_progress'
                executed_actions.append(action['action_type'])
                # Here you would execute the actual remediation command
                # For example: 
                # import subprocess
                # result = subprocess.run(action['command'].split(), capture_output=True, text=True)
                # action['result'] = result.stdout
                
                # Simulate successful execution
                action['status'] = 'success'
                action['result'] = f"Command executed successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Update incident status
    incident['status'] = 'remediating'
    
    return jsonify({
        "message": "Remediation approved and initiated successfully",
        "incident_id": incident_id,
        "status": incident['status'],
        "executed_actions": executed_actions,
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/api/incidents/<int:incident_id>/pdf', methods=['GET'])
def download_incident_pdf(incident_id):
    """
    Generate and download PDF report for a specific incident
    Requires: pip install reportlab
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
    except ImportError:
        return jsonify({"error": "reportlab library not installed. Run: pip install reportlab"}), 500
    
    incident = next((inc for inc in incidents_db if inc['id'] == incident_id), None)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title = Paragraph(f"<b>Incident Report #{incident['id']}</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.3*inch))
    
    # Incident Details
    story.append(Paragraph("<b>Incident Details</b>", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"<b>Title:</b> {incident['title']}", styles['Normal']))
    story.append(Paragraph(f"<b>Severity:</b> {incident['severity'].upper()}", styles['Normal']))
    story.append(Paragraph(f"<b>Status:</b> {incident['status']}", styles['Normal']))
    story.append(Paragraph(f"<b>Namespace:</b> {incident['namespace']}", styles['Normal']))
    story.append(Paragraph(f"<b>Resource:</b> {incident['resource_type']} / {incident['resource_name']}", styles['Normal']))
    story.append(Paragraph(f"<b>Detected At:</b> {incident['detected_at']}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # RCA Section
    if incident.get('rca'):
        story.append(Paragraph("<b>Root Cause Analysis</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(f"<b>Root Cause:</b> {incident['rca']['root_cause']}", styles['Normal']))
        story.append(Paragraph(f"<b>Confidence Score:</b> {incident['rca']['confidence_score'] * 100:.0f}%", styles['Normal']))
        story.append(Paragraph(f"<b>Analysis:</b> {incident['rca']['analysis']}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        if incident['rca'].get('recommendations'):
            story.append(Paragraph("<b>Recommendations:</b>", styles['Normal']))
            story.append(Spacer(1, 0.05*inch))
            for rec in incident['rca']['recommendations']:
                story.append(Paragraph(f"• {rec}", styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
    
    # Actions Section
    if incident.get('actions') and len(incident['actions']) > 0:
        story.append(Paragraph("<b>Remediation Actions</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        for i, action in enumerate(incident['actions'], 1):
            story.append(Paragraph(f"<b>Action {i}:</b> {action['action_type']}", styles['Normal']))
            story.append(Paragraph(f"<b>Status:</b> {action['status']}", styles['Normal']))
            if action.get('command'):
                story.append(Paragraph(f"<b>Command:</b> <font name='Courier'>{action['command']}</font>", styles['Normal']))
            if action.get('result'):
                story.append(Paragraph(f"<b>Result:</b> {action['result']}", styles['Normal']))
            story.append(Spacer(1, 0.15*inch))
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"<i>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'attachment; filename=incident-{incident_id}-report.pdf'
    }


if __name__ == '__main__':
    print("Starting Flask API server...")
    print("Install dependencies: pip install flask flask-cors reportlab")
    app.run(debug=True, port=5000)
